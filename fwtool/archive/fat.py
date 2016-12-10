"""A parser for FAT file system images"""

from stat import *
import time

from . import *
from ..io import *
from ..util import *

FatHeader = Struct('FatHeader', [
 ('jump', Struct.STR % 3),
 ('oemName', Struct.STR % 8),
 ('bytesPerSector', Struct.INT16),
 ('sectorsPerCluster', Struct.INT8),
 ('reservedSectors', Struct.INT16),
 ('fatCopies', Struct.INT8),
 ('rootEntries', Struct.INT16),
 ('sectors', Struct.INT16),
 ('mediaDescriptor', Struct.INT8),
 ('sectorsPerFat', Struct.INT16),
 ('...', 14),
 ('extendedSignature', Struct.STR % 1),
 ('serialNumber', Struct.INT32),
 ('volumeLabel', Struct.STR % 11),
 ('fsType', Struct.STR % 8),
 ('...', 448),
 ('signature', Struct.STR % 2),
])
fatHeaderSignature = b'\x55\xaa'
fatHeaderExtendedSignature = b'\x29'

FatDirEntry = Struct('FatDirEntry', [
 ('name', Struct.STR % 8),
 ('ext', Struct.STR % 3),
 ('attr', Struct.INT8),
 ('...', 10),
 ('time', Struct.INT16),
 ('date', Struct.INT16),
 ('cluster', Struct.INT16),
 ('size', Struct.INT32),
])

VfatDirEntry = Struct('VfatDirEntry', [
 ('sequence', Struct.INT8),
 ('name1', Struct.STR % 10),
 ('...', 3),
 ('name2', Struct.STR % 12),
 ('...', 2),
 ('name3', Struct.STR % 4),
])

def isFat(file):
 header = FatHeader.unpack(file)
 return header and header.signature == fatHeaderSignature and header.extendedSignature == fatHeaderExtendedSignature and header.fsType.startswith(b'FAT')

def readFat(file):
 header = FatHeader.unpack(file)

 if header.signature != fatHeaderSignature or header.extendedSignature != fatHeaderExtendedSignature:
  raise Exception('Wrong magic')

 fatOffset = header.reservedSectors * header.bytesPerSector
 rootOffset = fatOffset + header.fatCopies * header.sectorsPerFat * header.bytesPerSector
 dataOffset = rootOffset + ((header.rootEntries * FatDirEntry.size - 1) // header.bytesPerSector + 1) * header.bytesPerSector

 file.seek(fatOffset)
 if header.fsType == b'FAT12   ':
  endMarker = 0xfff
  packedClusters = [parse32le(file.read(3) + b'\0') for i in range(0, header.sectorsPerFat * header.bytesPerSector, 3)]
  clusters = [cluster for packed in packedClusters for cluster in [packed & 0xfff, (packed >> 12) & 0xfff]]
 elif header.fsType == b'FAT16   ':
  endMarker = 0xffff
  clusters = [parse16le(file.read(2)) for i in range(0, header.sectorsPerFat * header.bytesPerSector, 2)]
 else:
  raise Exception('Unknown FAT width')

 def readDir(entries, path=''):
  offset = 0
  vfatName = b''
  while entries[offset:offset+1] != b'\0':
   entry = FatDirEntry.unpack(entries, offset)
   if entry.name[0:1] != b'\xe5':
    if entry.attr == 0x0f:
     # VFAT
     vfatEntry = VfatDirEntry.unpack(entries, offset)
     vfatName = vfatEntry.name1 + vfatEntry.name2 + vfatEntry.name3 + vfatName
    else:
     if vfatName != b'':
      name = vfatName.decode('utf16').rstrip(u'\0\uffff')
      vfatName = b''
     else:
      name = entry.name.decode('ascii').rstrip(' ')
      if name[0] == '\x05':
       name = '\xe5' + name[1:]
      ext = entry.ext.decode('ascii').rstrip(' ')
      if ext != '':
       name += '.' + ext

     if name != '.' and name != '..':
      isDir = entry.attr & 0x10

      def generateChunks(cluster=entry.cluster, size=entry.size, isDir=isDir):
       read = 0
       while cluster != 0 and cluster != endMarker and (read < size or isDir):
        file.seek(dataOffset + (cluster - 2) * header.sectorsPerCluster * header.bytesPerSector)
        block = file.read(header.sectorsPerCluster * header.bytesPerSector)
        yield block if isDir else block[:size-read]
        read += len(block)
        cluster = clusters[cluster]

      contents = ChunkedFile(generateChunks, entry.size if not isDir else -1)
      yield UnixFile(
       path = path + '/' + name,
       size = entry.size,
       mtime = time.mktime((1980 + (entry.date >> 9), (entry.date >> 5) & 0xf, entry.date & 0x1f, entry.time >> 11, (entry.time >> 5) & 0x3f, (entry.time & 0x1f) * 2, -1, -1, -1)),
       mode = S_IFDIR if isDir else S_IFREG,
       uid = 0,
       gid = 0,
       contents = contents if not isDir else None,
      )

      if isDir:
       for f in readDir(contents.read(), path + '/' + name):
        yield f

   offset += FatDirEntry.size

 file.seek(rootOffset)
 for f in readDir(file.read(dataOffset - rootOffset)):
  yield f
