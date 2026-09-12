"""A simple parser for Microsoft cabinet archives"""

from collections import namedtuple
import time

from ..io import ChunkedFile
from ..lzx import inflateLzx
from ..util import *

CabFile = namedtuple('CabFile', 'path, size, mtime, contents')

CabHeader = Struct('CabHeader', [
 ('magic', Struct.STR % 4),
 ('...', 4),
 ('size', Struct.INT32),
 ('...', 4),
 ('fileOffset', Struct.INT32),
 ('...', 4),
 ('versionMinor', Struct.INT8),
 ('versionMajor', Struct.INT8),
 ('folderCount', Struct.INT16),
 ('fileCount', Struct.INT16),
 ('flags', Struct.INT16),
 ('setId', Struct.INT16),
 ('cabinetIndex', Struct.INT16),
])
cabHeaderMagic = b'MSCF'

CabReserveHeader = Struct('CabReserveHeader', [
 ('headerSize', Struct.INT16),
 ('folderSize', Struct.INT8),
 ('dataSize', Struct.INT8),
])

CabFolderHeader = Struct('CabFolderHeader', [
 ('dataOffset', Struct.INT32),
 ('dataCount', Struct.INT16),
 ('compression', Struct.INT16),
])

CabFileHeader = Struct('CabFileHeader', [
 ('size', Struct.INT32),
 ('folderOffset', Struct.INT32),
 ('folderIndex', Struct.INT16),
 ('date', Struct.INT16),
 ('time', Struct.INT16),
 ('attributes', Struct.INT16),
])

CabDataHeader = Struct('CabDataHeader', [
 ('checksum', Struct.INT32),
 ('compressedSize', Struct.INT16),
 ('uncompressedSize', Struct.INT16),
])

flagReservePresent = 0x4
flagPrevCabinet = 0x1
flagNextCabinet = 0x2

compressionNone = 0
compressionLzx = 3

def findCab(paths):
 """Guesses the .cab file from a list of filenames"""
 return [path for path in paths if path.lower().endswith('.cab')][0]

def readString(file):
 name = b''
 while True:
  char = file.read(1)
  if char == b'' or char == b'\0':
   return name
  name += char

def readDataBlocks(file, folder, reserveSize):
 offset = folder.dataOffset
 for i in range(folder.dataCount):
  header = CabDataHeader.unpack(file, offset)
  file.read(reserveSize)
  yield file.read(header.compressedSize)
  offset += CabDataHeader.size + reserveSize + header.compressedSize

def readFolder(file, folder, size, reserveSize):
 """Decompresses a folder and yields its contents"""
 compression = folder.compression & 0xf
 if compression == compressionNone:
  for block in readDataBlocks(file, folder, reserveSize):
   yield block
 elif compression == compressionLzx:
  for frame in inflateLzx(readDataBlocks(file, folder, reserveSize), (folder.compression >> 8) & 0x1f, size):
   yield frame
 else:
  raise Exception('Unsupported compression method')

def readFile(file, folder, size, reserveSize, start, length):
 def generateChunks():
  offset = 0
  for chunk in readFolder(file, folder, size, reserveSize):
   if offset + len(chunk) > start:
    yield chunk[max(start - offset, 0):start + length - offset]
   offset += len(chunk)
   if offset >= start + length:
    break
 return generateChunks

def isCab(file):
 """Returns true if the file provided is a cabinet archive"""
 header = CabHeader.unpack(file)
 return header is not None and header.magic == cabHeaderMagic

def readCab(file):
 """Takes a .cab file and returns the contained files"""
 header = CabHeader.unpack(file)
 if header.magic != cabHeaderMagic:
  raise Exception('Wrong magic')

 folderReserveSize = 0
 dataReserveSize = 0
 offset = CabHeader.size
 if header.flags & flagReservePresent:
  reserve = CabReserveHeader.unpack(file, offset)
  folderReserveSize = reserve.folderSize
  dataReserveSize = reserve.dataSize
  offset += CabReserveHeader.size + reserve.headerSize
 if header.flags & flagPrevCabinet:
  file.seek(offset)
  offset += len(readString(file)) + 1
  offset += len(readString(file)) + 1
 if header.flags & flagNextCabinet:
  file.seek(offset)
  offset += len(readString(file)) + 1
  offset += len(readString(file)) + 1

 folders = []
 for i in range(header.folderCount):
  folders.append(CabFolderHeader.unpack(file, offset))
  offset += CabFolderHeader.size + folderReserveSize

 files = []
 offset = header.fileOffset
 for i in range(header.fileCount):
  fileHeader = CabFileHeader.unpack(file, offset)
  name = readString(file).decode('latin1').replace('\\', '/')
  offset += CabFileHeader.size + len(name) + 1
  if fileHeader.folderIndex >= len(folders):
   raise Exception('Files spanning multiple cabinets are not supported')
  files.append((name, fileHeader))

 folderSizes = [0] * len(folders)
 for name, fileHeader in files:
  end = fileHeader.folderOffset + fileHeader.size
  if end > folderSizes[fileHeader.folderIndex]:
   folderSizes[fileHeader.folderIndex] = end

 for name, fileHeader in files:
  folder = folders[fileHeader.folderIndex]
  size = folderSizes[fileHeader.folderIndex]
  yield CabFile(
   path = name,
   size = fileHeader.size,
   mtime = time.mktime((
    1980 + (fileHeader.date >> 9),
    (fileHeader.date >> 5) & 0xf,
    fileHeader.date & 0x1f,
    fileHeader.time >> 11,
    (fileHeader.time >> 5) & 0x3f,
    (fileHeader.time & 0x1f) * 2,
    -1, -1, -1,
   )),
   contents = ChunkedFile(readFile(file, folder, size, dataReserveSize, fileHeader.folderOffset, fileHeader.size), fileHeader.size),
  )
