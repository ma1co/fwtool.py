"""A parser for FAT file system images"""

from stat import *
import time

from . import *
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
fatHeaderSignature = '\x55\xaa'
fatHeaderExtendedSignature = '\x29'

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

def isFat(data):
 if len(data) >= FatHeader.size:
  header = FatHeader.unpack(data)
  return header.signature == fatHeaderSignature and header.extendedSignature == fatHeaderExtendedSignature and header.fsType.startswith('FAT')
 return False

def readFat(data):
 header = FatHeader.unpack(data)

 if header.signature != fatHeaderSignature or header.extendedSignature != fatHeaderExtendedSignature:
  raise Exception('Wrong magic')

 fatOffset = header.reservedSectors * header.bytesPerSector
 rootOffset = fatOffset + header.fatCopies * header.sectorsPerFat * header.bytesPerSector
 dataOffset = rootOffset + ((header.rootEntries * FatDirEntry.size - 1) / header.bytesPerSector + 1) * header.bytesPerSector

 if header.fsType == 'FAT12   ':
  clusters = []
  endMarker = 0xfff
  for o in xrange(fatOffset, fatOffset + header.sectorsPerFat * header.bytesPerSector, 3):
   d = parse32le(data[o:o+4])
   clusters += [d & 0xfff, (d >> 12) & 0xfff]
 elif header.fsType == 'FAT16   ':
  clusters = [parse16le(data[o:o+2]) for o in xrange(fatOffset, fatOffset + header.sectorsPerFat * header.bytesPerSector, 2)]
  endMarker = 0xffff
 else:
  raise Exception('Unknown FAT width')

 files = {}
 def readDir(entries, path=''):
  offset = 0
  vfatName = ''
  while entries[offset] != '\x00':
   entry = FatDirEntry.unpack(entries, offset)
   if entry.name[0] != '\xe5':
    if entry.attr == 0x0f:
     # VFAT
     vfatEntry = VfatDirEntry.unpack(entries, offset)
     vfatName = vfatEntry.name1 + vfatEntry.name2 + vfatEntry.name3 + vfatName
    else:
     if vfatName != '':
      name = vfatName.decode('utf16').rstrip(u'\x00\uffff')
      vfatName = ''
     else:
      name = entry.name.rstrip(' ')
      if name[0] == '\x05':
       name = '\xe5' + name[1:]
      ext = entry.ext.rstrip(' ')
      if ext != '':
       name += '.' + ext

     if name != '.' and name != '..':
      isDir = entry.attr & 0x10

      contents = ''
      cluster = entry.cluster
      while cluster != 0 and cluster != endMarker:
       o = dataOffset + (cluster - 2) * header.sectorsPerCluster * header.bytesPerSector
       contents += data[o:o + header.sectorsPerCluster * header.bytesPerSector]
       cluster = clusters[cluster]

      files[path + '/' + name] = UnixFile(
       size = entry.size,
       mtime = time.mktime((1980 + (entry.date >> 9), (entry.date >> 5) & 0xf, entry.date & 0x1f, entry.time >> 11, (entry.time >> 5) & 0x3f, (entry.time & 0x1f) * 2, -1, -1, -1)),
       mode = S_IFDIR if isDir else S_IFREG,
       uid = 0,
       gid = 0,
       contents = contents[:entry.size] if not isDir else None,
      )

      if isDir:
       readDir(contents, path + '/' + name)

   offset += FatDirEntry.size

 readDir(data[rootOffset:dataOffset])
 return files
