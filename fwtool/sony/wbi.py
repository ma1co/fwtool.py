"""Parser for warm boot images"""

from collections import namedtuple
import io

from .. import lz77
from ..io import *
from ..util import *

WbiChunk = namedtuple('WbiChunk', 'physicalAddr, virtualAddr, size, contents')

WbiHeader = Struct('WbiHeader', [
 ('magic', Struct.STR % 4),
 ('numSections', Struct.INT32),
 ('flag', Struct.INT32),
 ('resumeVector', Struct.INT32),
 ('version', Struct.INT32),
 ('sectorSize', Struct.INT32),
 ('dataSize', Struct.INT32),
 ('kernelStart', Struct.INT32),
 ('kernelSize', Struct.INT32),
 ('kernelChecksum', Struct.INT32),
 ('oDataSize', Struct.INT32),
])
wbiHeaderMagic = b'WBI1'
wbiHeaderVersion = 0x20060224
wbiFlagCompressed = 1

WbiSectionHeader = Struct('WbiSectionHeader', [
 ('addr', Struct.INT32),
 ('size', Struct.INT32),
 ('checksum', Struct.INT32),
 ('flag', Struct.INT32),
 ('osize', Struct.INT32),
 ('virt', Struct.INT32),
 ('pad', Struct.INT32),
 ('metaChecksum', Struct.INT32),
])

def isWbi(file):
 header = WbiHeader.unpack(file)
 return header and header.magic == wbiHeaderMagic

def readWbi(file):
 header = WbiHeader.unpack(file)

 if header.magic != wbiHeaderMagic:
  raise Exception('Wrong magic')

 if header.version != wbiHeaderVersion:
  raise Exception('Wrong version')

 if not (header.flag & wbiFlagCompressed):
  raise Exception('Uncompressed WBI is not supported')

 # Skip empty sectors:
 wbiHeaderSize = header.sectorSize
 while True:
  file.seek(wbiHeaderSize)
  sector = file.read(header.sectorSize)
  if sector != len(sector) * b'\0' and sector != len(sector) * b'\xff':
   break
  wbiHeaderSize += header.sectorSize

 offset = 0
 for i in range(header.numSections):
  section = WbiSectionHeader.unpack(file, wbiHeaderSize + header.dataSize + i * WbiSectionHeader.size)

  def generateChunks(offset=offset, section=section):
   file.seek(wbiHeaderSize + offset)
   block = io.BytesIO(file.read(section.size))
   read = 0
   while read < section.osize:
    contents = lz77.inflateLz77(block)
    yield contents
    read += len(contents)

  yield WbiChunk(section.addr, section.virt, section.osize, ChunkedFile(generateChunks))
  offset += section.size
