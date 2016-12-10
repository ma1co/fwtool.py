"""A parser for cramfs file system images"""

from collections import namedtuple, OrderedDict
import io
import os
import posixpath
from stat import *
import zlib

from . import *
from ..io import *
from .. import lz77
from ..util import *

CramfsSuper = Struct('CramfsSuper', [
 ('magic', Struct.STR % 4),
 ('size', Struct.INT32),
 ('flags', Struct.INT32),
 ('future', Struct.INT32),
 ('signature', Struct.STR % 16),
 ('crc', Struct.INT32),
 ('edition', Struct.INT32),
 ('blocks', Struct.INT32),
 ('files', Struct.INT32),
 ('name', Struct.STR % 16),
])
cramfsBlockSize = 4096
cramfsSuperMagic = b'\x45\x3d\xcd\x28'
cramfsSuperSignature = b'Compressed ROMFS'

CramfsInode = Struct('CramfsInode', [
 ('mode', Struct.INT16),
 ('uid', Struct.INT16),
 ('size_gid', Struct.INT32),
 ('nameLen_offset', Struct.INT32),
])

def isCramfs(file):
 super = CramfsSuper.unpack(file)
 return super and super.magic == cramfsSuperMagic and super.signature == cramfsSuperSignature

def readCramfs(file):
 super = CramfsSuper.unpack(file)

 if super.flags & 0x10000000:
  raise Exception('LZO compression not supported')
 elif super.flags & 0x20000000:
  decompress = lambda data: lz77.inflateLz77(io.BytesIO(data))
 else:
  decompress = zlib.decompress

 if super.magic != cramfsSuperMagic or super.signature != cramfsSuperSignature:
  raise Exception('Wrong magic')

 if crc32(FilePart(file, 0, 32), io.BytesIO(4 * b'\0'), FilePart(file, 36)) != super.crc:
  raise Exception('Wrong checksum')

 def readInode(path=''):
  off = file.tell()
  inode = CramfsInode.unpack(file, off)

  size = inode.size_gid & 0xffffff
  gid = inode.size_gid >> 24
  nameLen = (inode.nameLen_offset & 0x3f) * 4
  offset = (inode.nameLen_offset >> 6) * 4
  file.seek(off + CramfsInode.size)
  name = file.read(nameLen).rstrip(b'\0').decode('ascii')

  path += name
  isDir = S_ISDIR(inode.mode)

  def generateChunks(offset=offset, size=size):
   nBlocks = (size - 1) // cramfsBlockSize + 1
   file.seek(offset)
   blockPointers = [offset + nBlocks * 4] + [parse32le(file.read(4)) for i in range(nBlocks)]
   for i in range(len(blockPointers) - 1):
    file.seek(blockPointers[i])
    block = file.read(blockPointers[i+1] - blockPointers[i])
    yield decompress(block)

  yield UnixFile(
   path = path,
   size = size if not isDir else 0,
   mtime = 0,
   mode = inode.mode,
   uid = inode.uid,
   gid = gid,
   contents = ChunkedFile(generateChunks, size) if S_ISREG(inode.mode) or S_ISLNK(inode.mode) else None,
  )

  if isDir:
   file.seek(offset)
   while file.tell() < offset + size:
    for f in readInode(path + '/'):
     yield f

  file.seek(off + CramfsInode.size + nameLen)

 file.seek(CramfsSuper.size)
 for f in readInode():
  yield f

def _pad(file, n, char=b'\0'):
 off = file.tell()
 if off % n > 0:
  file.write(char * (n - off % n))

def writeCramfs(files, outFile):
 files = {f.path: f for f in files}
 tree = {'': set()}
 for path in files:
  while path != '':
   parent = posixpath.dirname(path).rstrip('/')
   tree.setdefault(parent, set()).add(path)
   path = parent

 outFile.seek(0)
 outFile.write(b'\0' * CramfsSuper.size)

 stack = OrderedDict()
 StackItem = namedtuple('StackItem', 'inodeOffset, inodeSize, file, childrenPaths')
 tail = ['']
 while tail:
  file = files.get(tail[0], UnixFile(tail[0], 0, 0, S_IFDIR | 0o775, 0, 0, None))
  childrenPaths = sorted(tree.get(file.path, set()))

  offset = outFile.tell()
  outFile.write(b'\0' * CramfsInode.size)
  outFile.write(posixpath.basename(file.path).encode('ascii'))
  _pad(outFile, 4)

  stack[file.path] = StackItem(offset, outFile.tell() - offset, file, childrenPaths)
  tail = tail[1:] + childrenPaths

 blocks = 0
 for item in stack.values():
  if S_ISDIR(item.file.mode):
   if item.childrenPaths:
    offset = stack[item.childrenPaths[0]].inodeOffset
    size = stack[item.childrenPaths[-1]].inodeOffset + stack[item.childrenPaths[-1]].inodeSize - offset
   else:
    offset = 0
    size = 0
  else:
   offset = outFile.tell()
   item.file.contents.seek(0, os.SEEK_END)
   size = item.file.contents.tell()

   nBlocks = (size - 1) // cramfsBlockSize + 1
   blocks += nBlocks
   outFile.write(b'\0' * (nBlocks * 4))

   item.file.contents.seek(0)
   for i in range(nBlocks):
    outFile.write(zlib.compress(item.file.contents.read(cramfsBlockSize), 9))
    o = outFile.tell()
    outFile.seek(offset + i * 4)
    outFile.write(dump32le(o))
    outFile.seek(o)
   _pad(outFile, 4)

  o = outFile.tell()
  outFile.seek(item.inodeOffset)
  outFile.write(CramfsInode.pack(
   mode = item.file.mode,
   uid = item.file.uid,
   size_gid = item.file.gid << 24 | size,
   nameLen_offset = (offset // 4) << 6 | (item.inodeSize - CramfsInode.size) // 4
  ))
  outFile.seek(o)

 _pad(outFile, cramfsBlockSize)
 size = outFile.tell()

 outFile.seek(0)
 outFile.write(CramfsSuper.pack(
  magic = cramfsSuperMagic,
  size = size,
  flags = 3,
  future = 0,
  signature = cramfsSuperSignature,
  crc = 0,
  edition = 0,
  blocks = blocks,
  files = len(stack),
  name = b'Compressed',
 ))

 outFile.seek(0)
 crc = crc32(outFile)
 outFile.seek(32)
 outFile.write(dump32le(crc))
