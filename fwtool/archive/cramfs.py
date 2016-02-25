"""A parser for cramfs file system images"""

from stat import *
import zlib

from . import *
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

def isCramfs(data):
 if len(data) >= CramfsSuper.size:
  super = CramfsSuper.unpack(data)
  return super.magic == cramfsSuperMagic and super.signature == cramfsSuperSignature
 return False

def readCramfs(data):
 super = CramfsSuper.unpack(data)

 if super.magic != cramfsSuperMagic or super.signature != cramfsSuperSignature:
  raise Exception('Wrong magic')

 if crc32(data[:32] + 4*'\x00' + data[36:]) != super.crc:
  raise Exception('Wrong checksum')

 files = {}
 def readInode(data, off, path=''):
  inode = CramfsInode.unpack(data, off)

  size = inode.size_gid & 0xffffff
  gid = inode.size_gid >> 24
  nameLen = (inode.nameLen_offset & 0x3f) * 4
  offset = (inode.nameLen_offset >> 6) * 4
  name = data[off+CramfsInode.size:off+CramfsInode.size+nameLen].rstrip('\0')

  path += name
  isDir = S_ISDIR(inode.mode)

  if not isDir:
   nBlocks = (size - 1) / cramfsBlockSize + 1
   blockPointers = [offset+nBlocks*4] + [parse32le(data[i:i+4]) for i in xrange(offset, offset+nBlocks*4, 4)]
   blocks = [data[blockPointers[i]:blockPointers[i+1]] for i in xrange(len(blockPointers) - 1)]
   contents = ''.join(zlib.decompress(block) for block in blocks)
  else:
   contents = None

  files[path] = UnixFile(
   size = size if not isDir else 0,
   mtime = 0,
   mode = inode.mode,
   uid = inode.uid,
   gid = gid,
   contents = contents
  )

  if isDir:
   end = offset + size
   while offset < end:
    offset += readInode(data, offset, path + '/')

  return CramfsInode.size + nameLen

 readInode(data, CramfsSuper.size)
 return files
