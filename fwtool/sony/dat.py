"""Parser for the .dat file contained in the updater executable"""

from collections import namedtuple
import io
import re
import shutil

from ..io import FilePart
from ..util import *

DatFile = namedtuple('DatFile', 'normalUsbDescriptors, updaterUsbDescriptors, isLens, firmwareData')

DatHeader = Struct('DatHeader', [
 ('magic', Struct.STR % 8),
])
datHeaderMagic = b'\x89\x55\x46\x55\x0d\x0a\x1a\x0a'

DatChunkHeader = Struct('DatChunkHeader', [
 ('size', Struct.INT32),
 ('type', Struct.STR % 4),
], Struct.BIG_ENDIAN)

DatvChunk = Struct('DatvChunk', [
 ('dataVersion', Struct.INT16),
 ('isLens', Struct.INT16),
], Struct.BIG_ENDIAN)
datvChunkType = b'DATV'
datvDataVersion = 0x100

ProvChunk = Struct('ProvChunk', [
 ('protocolVersion', Struct.INT16),
 ('reserved', 2),
], Struct.BIG_ENDIAN)
provChunkType = b'PROV'
provProtocolVersion = 0x100

UdidChunkHeader = Struct('UdidChunkHeader', [
 ('descriptorCount', Struct.INT32),
], Struct.BIG_ENDIAN)
udidChunkType = b'UDID'

UdidChunkDescriptor = Struct('UdidChunkDescriptor', [
 ('pid', Struct.INT16),
 ('vid', Struct.INT16),
 ('mode', Struct.INT8),
 ('reserved', 3),
], Struct.BIG_ENDIAN)
descriptorTypeNormal = 1
descriptorTypeUpdater = 2

fdatChunkType = b'FDAT'

DendChunk = Struct('DendChunk', [
 ('crc', Struct.INT32),
], Struct.BIG_ENDIAN)
dendChunkType = b'DEND'

def findDat(paths):
 """Guesses the .dat file from a list of filenames"""
 return [path for path in paths if re.search('/FirmwareData_([^/]+)\.dat$', path)][0]

def isDat(file):
 """Returns true if the data provided is a dat file"""
 header = DatHeader.unpack(file)
 return header and header.magic == datHeaderMagic

def readChunks(file):
 header = DatHeader.unpack(file)

 if header.magic != datHeaderMagic:
  raise Exception('Wrong magic')

 chunks = []
 offset = DatHeader.size
 while True:
  chunk = DatChunkHeader.unpack(file, offset)
  offset += DatChunkHeader.size
  chunks.append((chunk.type, FilePart(file, offset, chunk.size)))
  offset += chunk.size
  if chunk.type == dendChunkType:
   break

 return chunks, offset

def writeChunks(chunks, file):
 file.seek(0)
 file.write(DatHeader.pack(magic=datHeaderMagic))
 offset = DatHeader.size

 for type, contents in chunks:
  file.seek(offset)
  file.write(b'\0' * DatChunkHeader.size)
  contents.seek(0)
  shutil.copyfileobj(contents, file)
  file.seek(offset)
  file.write(DatChunkHeader.pack(type=type, size=contents.tell()))
  offset += DatChunkHeader.size + contents.tell()

 return offset

def _calcCrc(file, fileSize):
 return crc32(FilePart(file, 0, fileSize - DatChunkHeader.size - DendChunk.size))

def readDat(file):
 """Reads a .dat file"""
 chunkList, fileSize = readChunks(file)
 chunks = dict(chunkList)

 datv = DatvChunk.unpack(chunks[datvChunkType])
 if datv.dataVersion != datvDataVersion or datv.isLens not in [0, 1]:
  raise Exception('Wrong data version')

 prov = ProvChunk.unpack(chunks[provChunkType])
 if prov.protocolVersion != provProtocolVersion:
  raise Exception('Wrong protocol version')

 descriptors = {descriptorTypeNormal: [], descriptorTypeUpdater: []}
 for i in range(UdidChunkHeader.unpack(chunks[udidChunkType]).descriptorCount):
  descriptor = UdidChunkDescriptor.unpack(chunks[udidChunkType], UdidChunkHeader.size + i * UdidChunkDescriptor.size)
  descriptors[descriptor.mode].append((descriptor.vid, descriptor.pid))

 dend = DendChunk.unpack(chunks[dendChunkType])
 if _calcCrc(file, fileSize) != dend.crc:
  raise Exception('Wrong checksum')

 return DatFile(
  normalUsbDescriptors = descriptors[descriptorTypeNormal],
  updaterUsbDescriptors = descriptors[descriptorTypeUpdater],
  isLens = bool(datv.isLens),
  firmwareData = chunks[fdatChunkType],
 )

def writeDat(dat, file):
 descriptors = [(descriptorTypeNormal, dat.normalUsbDescriptors), (descriptorTypeUpdater, dat.updaterUsbDescriptors)]
 udidChunk = io.BytesIO()
 udidChunk.write(UdidChunkHeader.pack(descriptorCount=sum(len(descs) for type, descs in descriptors)))
 for type, descs in descriptors:
  for vid, pid in descs:
   udidChunk.write(UdidChunkDescriptor.pack(vid=vid, pid=pid, mode=type))

 fileSize = writeChunks([
  (datvChunkType, io.BytesIO(DatvChunk.pack(dataVersion=datvDataVersion, isLens=dat.isLens))),
  (provChunkType, io.BytesIO(ProvChunk.pack(protocolVersion=provProtocolVersion))),
  (udidChunkType, udidChunk),
  (fdatChunkType, dat.firmwareData),
  (dendChunkType, io.BytesIO(b'\0' * DendChunk.size)),
 ], file)

 crc = _calcCrc(file, fileSize)
 file.seek(fileSize - DendChunk.size)
 file.write(DendChunk.pack(crc=crc))
