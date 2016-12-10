"""A parser for ext2 file system images"""

from stat import *

from . import *
from ..io import *
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
ext2HeaderMagic = b'\x53\xef'

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

def isExt2(file):
 header = Ext2Header.unpack(file)
 return header and header.magic == ext2HeaderMagic

def readExt2(file):
 header = Ext2Header.unpack(file)

 if header.magic != ext2HeaderMagic:
  raise Exception('Wrong magic')

 blockSize = 1024 << header.blockSize

 bdgOffset = max(blockSize, 2048)
 numBlockGroups = (header.blocksCount-1) // header.blocksPerGroup + 1
 inodeTables = [Ext2Bgd.unpack(file, bdgOffset + i * Ext2Bgd.size).inodeTableBlock for i in range(numBlockGroups)]

 def readInode(i, path = ''):
  inode = Ext2Inode.unpack(file, inodeTables[(i-1) // header.inodesPerGroup] * blockSize + ((i-1) % header.inodesPerGroup) * Ext2Inode.size)

  def generateChunks(contents=inode.blocks, size=inode.size, mode=inode.mode):
   if S_ISLNK(mode) and size <= len(contents):
    # Fast symlinks
    yield contents[:size]
    return

   ptrs = []
   for i in range(15, 11, -1):
    # resolve indirect pointers
    contents = contents[:i*4]
    for ptr in ptrs[i:]:
     if ptr != 0:
      file.seek(ptr * blockSize)
      contents += file.read(blockSize)
    ptrs = [parse32le(contents[j:j+4]) for j in range(0, len(contents), 4)]

   read = 0
   for ptr in ptrs:
    if read < size:
     if ptr == 0:
      block = b'\0' * blockSize
     else:
      file.seek(ptr * blockSize)
      block = file.read(blockSize)
     yield block[:size-read]
     read += len(block)

  isDir = S_ISDIR(inode.mode)

  contents = ChunkedFile(generateChunks, inode.size)
  yield UnixFile(
   path = path,
   size = inode.size if not isDir else 0,
   mtime = inode.mtime,
   mode = inode.mode,
   uid = inode.uid,
   gid = inode.gid,
   contents = contents if S_ISREG(inode.mode) or S_ISLNK(inode.mode) else None,
  )

  if isDir:
   while contents.tell() < inode.size:
    entry = Ext2DirEntry.unpack(contents.read(Ext2DirEntry.size))
    name = contents.read(entry.nameSize).decode('ascii')
    if name != '.' and name != '..':
     for f in readInode(entry.inode, path + '/' + name):
      yield f
    contents.read(entry.size - Ext2DirEntry.size - entry.nameSize)

 for f in readInode(2):
  yield f
