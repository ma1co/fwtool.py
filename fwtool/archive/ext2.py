"""A parser for ext2 file system images"""

from stat import *

from . import *
from ..util import *

Ext2Header = Struct('Ext2Header', [
 ('bootRecord', 1024),
 ('inodesCount', Struct.INT32),
 ('blocksCount', Struct.INT32),
 ('...', 16),
 ('blockSize', Struct.INT32),
 ('...', 4),
 ('blocksPerGroup', Struct.INT32),
 ('...', 4),
 ('inodesPerGroup', Struct.INT32),
 ('...', 12),
 ('magic', Struct.STR % 2),
 ('...', 966),
])
ext2HeaderMagic = '\x53\xef'

Ext2Bgd = Struct('Ext2BlockGroupDescriptor', [
 ('...', 8),
 ('inodeTableBlock', Struct.INT32),
 ('...', 20),
])

Ext2Inode = Struct('Ext2Inode', [
 ('mode', Struct.INT16),
 ('uid', Struct.INT16),
 ('size', Struct.INT32),
 ('atime', Struct.INT32),
 ('ctime', Struct.INT32),
 ('mtime', Struct.INT32),
 ('dtime', Struct.INT32),
 ('gid', Struct.INT16),
 ('...', 14),
 ('blocks', Struct.STR % 60),
 ('...', 28),
])

Ext2DirEntry = Struct('Ext2DirEntry', [
 ('inode', Struct.INT32),
 ('size', Struct.INT16),
 ('nameSize', Struct.INT8),
 ('fileType', Struct.INT8),
])

def isExt2(data):
 return len(data) >= Ext2Header.size and Ext2Header.unpack(data).magic == ext2HeaderMagic

def readExt2(data):
 header = Ext2Header.unpack(data)

 if header.magic != ext2HeaderMagic:
  raise Exception('Wrong magic')

 blockSize = 1024 << header.blockSize

 bdgOffset = max(blockSize, 2048)
 numBlockGroups = (header.blocksCount - 1) / header.blocksPerGroup + 1
 inodeTables = [Ext2Bgd.unpack(data, bdgOffset + i * Ext2Bgd.size).inodeTableBlock for i in xrange(numBlockGroups)]

 files = {}
 def readInode(i, path = ''):
  inode = Ext2Inode.unpack(data, inodeTables[(i-1)/header.inodesPerGroup] * blockSize + ((i-1)%header.inodesPerGroup) * Ext2Inode.size)

  contents = inode.blocks
  for i in [56, 52, 48, 0]:
   ptrs = [parse32le(contents[j:j+4]) for j in xrange(i, len(contents), 4)]
   contents = contents[:i] + ''.join([data[ptr*blockSize:(ptr+1)*blockSize] for ptr in ptrs if ptr != 0])
  contents = contents[:inode.size]

  isDir = S_ISDIR(inode.mode)

  files[path] = UnixFile(
   size = inode.size if not isDir else 0,
   mtime = inode.mtime,
   mode = inode.mode,
   uid = inode.uid,
   gid = inode.gid,
   contents = contents if not isDir else None,
  )

  if isDir:
   offset = 0
   while offset < len(contents):
    entry = Ext2DirEntry.unpack(contents, offset)
    name = contents[offset+Ext2DirEntry.size:offset+Ext2DirEntry.size+entry.nameSize]
    if name != '.' and name != '..':
     readInode(entry.inode, path + '/' + name)
    offset += entry.size

 readInode(2)
 return files
