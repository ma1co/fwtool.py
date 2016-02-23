"""Parser for the .dat file contained in the updater executable"""

import re

import constants
from ..util import *

DatHeader = Struct('DatHeader', [
 ('magic', Struct.STR % 8),
])
datHeaderMagic = '\x89\x55\x46\x55\x0d\x0a\x1a\x0a'

DatChunk = Struct('DatChunk', [
 ('size', Struct.INT32),
 ('type', Struct.STR % 4),
], Struct.BIG_ENDIAN)

DendChunk = Struct('DendChunk', [
 ('crc', Struct.INT32),
], Struct.BIG_ENDIAN)

def findDat(paths):
 """Guesses the .dat file from a list of filenames"""
 return [path for path in paths if re.search('/FirmwareData_([^/]+)\.dat$', path)][0]

def isDat(data):
 """Returns true if the data provided is a dat file"""
 return len(data) >= DatHeader.size and DatHeader.unpack(data).magic == datHeaderMagic

def readDat(data):
 """Takes the contents of the .dat file and returns a dict containing the name and content of its chunks"""
 header = DatHeader.unpack(data)

 if header.magic != datHeaderMagic:
  raise Exception('Wrong magic')

 chunks = {}
 offset = DatHeader.size
 while 'DEND' not in chunks:
  chunk = DatChunk.unpack(data, offset)
  offset += DatChunk.size
  chunks[chunk.type] = memoryview(data)[offset:offset+chunk.size]
  offset += chunk.size

 dend = DendChunk.unpack(chunks['DEND'])
 if crc32(memoryview(data)[:offset-DatChunk.size-DendChunk.size]) != dend.crc:
  raise Exception('Wrong checksum')

 return chunks
