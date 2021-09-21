import io
from stat import *
import zlib

from . import *
from ..util import *

SquashfsSuper = Struct('SquashfsSuper', [
 ('magic', Struct.STR % 4),
 ('inodeCount', Struct.INT32),
 ('modificationTime', Struct.INT32),
 ('blockSize', Struct.INT32),
 ('fragmentEntryCount', Struct.INT32),
 ('compressionId', Struct.INT16),
 ('blockLog', Struct.INT16),
 ('flags', Struct.INT16),
 ('idCount', Struct.INT16),
 ('versionMajor', Struct.INT16),
 ('versionMinor', Struct.INT16),
 ('rootInodeRef', Struct.INT64),
 ('bytesUsed', Struct.INT64),
 ('idTableStart', Struct.INT64),
 ('xattrIdTableStart', Struct.INT64),
 ('inodeTableStart', Struct.INT64),
 ('directoryTableStart', Struct.INT64),
 ('fragmentTableStart', Struct.INT64),
 ('exportTableStart', Struct.INT64),
])
squashfsSuperMagic = b'hsqs'

SquashfsInodeHeader = Struct('SquashfsInodeHeader', [
 ('inodeType', Struct.INT16),
 ('permissions', Struct.INT16),
 ('uidIdx', Struct.INT16),
 ('gidIdx', Struct.INT16),
 ('modifiedTime', Struct.INT32),
 ('inodeNumber', Struct.INT32),
])
squashfsInodeTypeBasicDirectory = 1
squashfsInodeTypeBasicFile = 2
squashfsInodeTypeBasicSymlink = 3
squashfsInodeTypeExtendedDirectory = 8
squashfsInodeTypeExtendedFile = 9
squashfsInodeTypeExtendedSymlink = 10

SquashfsBasicDirectoryInode = Struct('SquashfsBasicDirectoryInode', [
 ('dirBlockStart', Struct.INT32),
 ('hardLinkCount', Struct.INT32),
 ('fileSize', Struct.INT16),
 ('blockOffset', Struct.INT16),
 ('parentInodeNumber', Struct.INT32),
])

SquashfsExtendedDirectoryInode = Struct('SquashfsExtendedDirectoryInode', [
 ('hardLinkCount', Struct.INT32),
 ('fileSize', Struct.INT32),
 ('dirBlockStart', Struct.INT32),
 ('parentInodeNumber', Struct.INT32),
 ('indexCount', Struct.INT16),
 ('blockOffset', Struct.INT16),
 ('xattrIdx', Struct.INT32),
])

SquashfsBasicFileInode = Struct('SquashfsBasicFileInode', [
 ('blocksStart', Struct.INT32),
 ('fragmentBlockIndex', Struct.INT32),
 ('blockOffset', Struct.INT32),
 ('fileSize', Struct.INT32),
])

SquashfsExtendedFileInode = Struct('SquashfsExtendedFileInode', [
 ('blocksStart', Struct.INT64),
 ('fileSize', Struct.INT64),
 ('sparse', Struct.INT64),
 ('hardLinkCount', Struct.INT32),
 ('fragmentBlockIndex', Struct.INT32),
 ('blockOffset', Struct.INT32),
 ('xattrIdx', Struct.INT32),
])

SquashfsSymlinkInode = Struct('SquashfsSymlinkInode', [
 ('hardLinkCount', Struct.INT32),
 ('targetSize', Struct.INT32),
])

SquashfsDirectoryHeader = Struct('SquashfsDirectoryHeader', [
 ('count', Struct.INT32),
 ('start', Struct.INT32),
 ('inodeNumber', Struct.INT32),
])

SquashfsDirectoryEntry = Struct('SquashfsDirectoryEntry', [
 ('offset', Struct.INT16),
 ('inodeOffset', Struct.INT16),
 ('type', Struct.INT16),
 ('nameSize', Struct.INT16),
])

SquashfsFragmentBlockEntry = Struct('SquashfsFragmentBlockEntry', [
 ('start', Struct.INT64),
 ('size', Struct.INT32),
 ('unused', 4),
])

def isSquashfs(file):
 super = SquashfsSuper.unpack(file)
 return super and super.magic == squashfsSuperMagic

def readSquashfs(file):
 super = SquashfsSuper.unpack(file)

 if super.magic != squashfsSuperMagic:
  raise Exception('Wrong magic')
 if super.versionMajor != 4 or super.versionMinor != 0:
  raise Exception('Wrong version')
 if (1 << super.blockLog) != super.blockSize:
  raise Exception('Wrong block size')
 if super.compressionId != 1:
  raise Exception('Compression unsupported')

 def readMetadata(start, offset, size):
  block = io.BytesIO()
  file.seek(start)
  while block.tell() < offset + size:
   header = parse16le(file.read(2))
   data = file.read(header & 0x7fff)
   if not (header & 0x8000):
    data = zlib.decompress(data)
   block.write(data)
  return block.getvalue()[offset:offset+size]

 def readTable(start, count, size):
  entriesPerBlock = 0x2000 // size
  file.seek(start)
  blockOffsets = [parse64le(file.read(8)) for i in range((count + entriesPerBlock - 1) // entriesPerBlock)]
  blocks = [readMetadata(o, 0, min(((count - i * entriesPerBlock) * size), 0x2000)) for i, o in enumerate(blockOffsets)]
  return [block[i:i+size] for block in blocks for i in range(0, len(block), size)]

 fragments = [SquashfsFragmentBlockEntry.unpack(entry) for entry in readTable(super.fragmentTableStart, super.fragmentEntryCount, SquashfsFragmentBlockEntry.size)]
 ids = [parse32le(entry) for entry in readTable(super.idTableStart, super.idCount, 4)]

 def readInode(start, offset, path=''):
  start += super.inodeTableStart
  inode = SquashfsInodeHeader.unpack(readMetadata(start, offset, SquashfsInodeHeader.size))

  if inode.inodeType in (squashfsInodeTypeBasicDirectory, squashfsInodeTypeExtendedDirectory):
   inodeStruct = SquashfsBasicDirectoryInode if inode.inodeType == squashfsInodeTypeBasicDirectory else SquashfsExtendedDirectoryInode
   f = inodeStruct.unpack(readMetadata(start, offset + SquashfsInodeHeader.size, inodeStruct.size))
   dir = io.BytesIO(readMetadata(super.directoryTableStart + f.dirBlockStart, f.blockOffset, f.fileSize - 3))

   yield UnixFile(
    path = path or '/',
    size = 0,
    mtime = inode.modifiedTime,
    mode = S_IFDIR | inode.permissions,
    uid = ids[inode.uidIdx],
    gid = ids[inode.gidIdx],
    contents = None,
   )

   while True:
    header = dir.read(SquashfsDirectoryHeader.size)
    if header == b'':
     break
    header = SquashfsDirectoryHeader.unpack(header)
    for i in range(header.count + 1):
     entry = SquashfsDirectoryEntry.unpack(dir.read(SquashfsDirectoryEntry.size))
     name = dir.read(entry.nameSize + 1).decode('ascii')
     for f in readInode(header.start, entry.offset, path + '/' + name):
      yield f

  elif inode.inodeType in (squashfsInodeTypeBasicFile, squashfsInodeTypeExtendedFile):
   inodeStruct = SquashfsBasicFileInode if inode.inodeType == squashfsInodeTypeBasicFile else SquashfsExtendedFileInode
   f = inodeStruct.unpack(readMetadata(start, offset + SquashfsInodeHeader.size, inodeStruct.size))
   blockCount = f.fileSize // super.blockSize if f.fragmentBlockIndex != 0xffffffff else (f.fileSize + super.blockSize - 1) // super.blockSize
   blockSizes = readMetadata(start, offset + SquashfsInodeHeader.size + inodeStruct.size, blockCount * 4)
   blockSizes = [parse32le(blockSizes[i:i+4]) for i in range(0, len(blockSizes), 4)]

   contents = io.BytesIO()
   file.seek(f.blocksStart)
   for blockSize in blockSizes:
    s = min(f.fileSize - contents.tell(), super.blockSize)
    if blockSize == 0:
     contents.write(b'\0' * s)
    else:
     block = file.read(blockSize & ~(1 << 24))
     if not (blockSize & (1 << 24)):
      block = zlib.decompress(block)
     contents.write(block.ljust(s, b'\0'))
   if f.fragmentBlockIndex != 0xffffffff:
    fragment = fragments[f.fragmentBlockIndex]
    file.seek(fragment.start)
    block = file.read(fragment.size & ~(1 << 24))
    if not (fragment.size & (1 << 24)):
     block = zlib.decompress(block)
    contents.write(block[f.blockOffset:f.blockOffset+f.fileSize-contents.tell()])

   contents.seek(0)
   yield UnixFile(
    path = path,
    size = f.fileSize,
    mtime = inode.modifiedTime,
    mode = S_IFREG | inode.permissions,
    uid = ids[inode.uidIdx],
    gid = ids[inode.gidIdx],
    contents = contents,
   )

  elif inode.inodeType in (squashfsInodeTypeBasicSymlink, squashfsInodeTypeExtendedSymlink):
   f = SquashfsSymlinkInode.unpack(readMetadata(start, offset + SquashfsInodeHeader.size, SquashfsSymlinkInode.size))
   target = readMetadata(start, offset + SquashfsInodeHeader.size + SquashfsSymlinkInode.size, f.targetSize)

   yield UnixFile(
    path = path,
    size = len(target),
    mtime = inode.modifiedTime,
    mode = S_IFLNK | inode.permissions,
    uid = ids[inode.uidIdx],
    gid = ids[inode.gidIdx],
    contents = io.BytesIO(target),
   )

  else:
   raise Exception('Unknown inode type')

 for f in readInode((super.rootInodeRef >> 16) & 0xffffffff, super.rootInodeRef & 0xffff):
  yield f
