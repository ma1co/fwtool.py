"""A parser for cramfs file system images"""

import io
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
cramfsSuperMagic = '\x45\x3d\xcd\x28'
cramfsSuperSignature = 'Compressed ROMFS'

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

 if crc32(FilePart(file, 0, 32), io.BytesIO(4 * '\x00'), FilePart(file, 36)) != super.crc:
  raise Exception('Wrong checksum')

 def readInode(path=''):
  off = file.tell()
  inode = CramfsInode.unpack(file, off)

  size = inode.size_gid & 0xffffff
  gid = inode.size_gid >> 24
  nameLen = (inode.nameLen_offset & 0x3f) * 4
  offset = (inode.nameLen_offset >> 6) * 4
  file.seek(off + CramfsInode.size)
  name = file.read(nameLen).rstrip('\0')

  path += name
  isDir = S_ISDIR(inode.mode)

  def generateChunks(offset=offset, size=size):
   nBlocks = (size - 1) / cramfsBlockSize + 1
   file.seek(offset)
   blockPointers = [offset + nBlocks * 4] + [parse32le(file.read(4)) for i in xrange(nBlocks)]
   for i in xrange(len(blockPointers) - 1):
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
