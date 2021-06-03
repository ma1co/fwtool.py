"""A parser for FAT file system images"""

import io
import posixpath
import shutil
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
 ('...', 1),
 ('ctimeCs', Struct.INT8),
 ('...', 8),
 ('time', Struct.INT16),
 ('date', Struct.INT16),
 ('cluster', Struct.INT16),
 ('size', Struct.INT32),
])

VfatDirEntry = Struct('VfatDirEntry', [
 ('sequence', Struct.INT8),
 ('name1', Struct.STR % 10),
 ('attr', Struct.INT8),
 ('...', 1),
 ('checksum', Struct.INT8),
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
      isLink = (entry.attr & 0x04) and (entry.ctimeCs & 0xe1) == 0x21
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
       mode = S_IFDIR if isDir else S_IFLNK if isLink else S_IFREG,
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


def writeFat(files, size, outFile):
 files = {f.path: f for f in files}
 tree = {'': set()}
 for path in files:
  while path != '':
   parent = posixpath.dirname(path).rstrip('/')
   tree.setdefault(parent, set()).add(path)
   path = parent

 sectorSize = 0x200
 clusterSize = 0x4000

 sectors = size // sectorSize
 fatSize = (size // clusterSize + 1) // 2 * 3
 fatSectors = (fatSize + sectorSize - 1) // sectorSize

 outFile.write(FatHeader.pack(
  jump = b'\xeb\0\x90',
  oemName = 8*b'\0',
  bytesPerSector = sectorSize,
  sectorsPerCluster = clusterSize // sectorSize,
  reservedSectors = 1,
  fatCopies = 1,
  rootEntries = clusterSize // FatDirEntry.size,
  sectors = sectors,
  mediaDescriptor = 0xf8,
  sectorsPerFat = fatSectors,
  extendedSignature = fatHeaderExtendedSignature,
  serialNumber = 0,
  volumeLabel = 11*b' ',
  fsType = b'FAT12   ',
  signature = fatHeaderSignature,
 ))
 for i in range(sectors - 1):
  outFile.write(sectorSize * b'\0')

 fatOffset = sectorSize
 rootOffset = fatOffset + fatSectors * sectorSize
 dataOffset = rootOffset + clusterSize

 clusters = [0xff8, 0xfff]
 def writeData(f):
  f.seek(0)
  outFile.seek(dataOffset + (len(clusters) - 2) * clusterSize)
  shutil.copyfileobj(f, outFile)
  nc = (f.tell() + clusterSize - 1) // clusterSize
  for i in range(nc):
   clusters.append(len(clusters) + 1 if i < nc-1 else 0xfff)
  return (len(clusters)-nc if nc else 0), f.tell()

 def dirEntries(pc, c):
  return FatDirEntry.pack(
    name = b'.       ',
    ext = b'   ',
    attr = 0x10,
    ctimeCs = 0,
    time = 0,
    date = 0,
    cluster = c,
    size = 0,
   ) + FatDirEntry.pack(
    name = b'..      ',
    ext = b'   ',
    attr = 0x10,
    ctimeCs = 0,
    time = 0,
    date = 0,
    cluster = pc,
    size = 0,
   )

 dirs = {}
 def writeDir(path):
  data = io.BytesIO()
  if path != '':
   data.write(dirEntries(0, 0))
  for p in tree.get(path, set()):
   file = files.get(p, UnixFile(p, 0, 0, S_IFDIR | 0o775, 0, 0, None))
   c, s = writeData(file.contents if not S_ISDIR(file.mode) else writeDir(file.path))
   if S_ISDIR(file.mode):
    dirs[file.path] = c

   name, ext = (posixpath.basename(file.path).upper() + '.').split('.', 1)
   name = name[:8].ljust(8, ' ').encode('ascii')
   ext = ext[:3].ljust(3, ' ').encode('ascii')
   sum = 0
   for chr in (name + ext):
    sum = (((sum & 1) << 7) + (sum >> 1) + chr) & 0xff

   fn = posixpath.basename(file.path) + '\0'
   vfatEntries = [fn[o:o+13] for o in range(0, len(fn), 13)]
   for i, n in list(enumerate(vfatEntries))[::-1]:
    n = n.encode('utf-16le').ljust(26, b'\xff')
    data.write(VfatDirEntry.pack(
     sequence = i + 1 + (0x40 if i == len(vfatEntries)-1 else 0),
     name1 = n[:10],
     attr = 0x0f,
     checksum = sum,
     name2 = n[10:22],
     name3 = n[22:],
    ))

   t = time.localtime(file.mtime)
   data.write(FatDirEntry.pack(
    name = name,
    ext = ext,
    attr = 0x10 if S_ISDIR(file.mode) else 0x04 if S_ISLNK(file.mode) else 0,
    ctimeCs = 0x21 if S_ISLNK(file.mode) else 0,
    time = (t.tm_hour << 11) + (t.tm_min << 5) + t.tm_sec // 2,
    date = (max(t.tm_year - 1980, 0) << 9) + (t.tm_mon << 5) + t.tm_mday,
    cluster = c,
    size = s if not S_ISDIR(file.mode) else 0,
   ))
  return data

 root = writeDir('')
 root.seek(0)
 outFile.seek(rootOffset)
 shutil.copyfileobj(root, outFile)

 for p, c in dirs.items():
  parent = posixpath.split(p)[0]
  outFile.seek(dataOffset + (c - 2) * clusterSize)
  outFile.write(dirEntries(dirs[parent] if parent != '/' else 0, c))

 outFile.seek(fatOffset)
 for i in range(0, len(clusters), 2):
  outFile.write(dump32le(clusters[i] + ((clusters[i+1] << 12) if i+1 < len(clusters) else 0))[:3])
