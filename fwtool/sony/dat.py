"""Parser for the .dat file contained in the updater executable"""

from collections import OrderedDict
import re

import constants
from ..io import FilePart
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

def isDat(file):
 """Returns true if the data provided is a dat file"""
 header = DatHeader.unpack(file)
 return header and header.magic == datHeaderMagic

def readDat(file):
 """Takes a .dat file and returns a dict of its chunks"""
 header = DatHeader.unpack(file)

 if header.magic != datHeaderMagic:
  raise Exception('Wrong magic')

 chunks = OrderedDict()
 offset = DatHeader.size
 while 'DEND' not in chunks:
  chunk = DatChunk.unpack(file, offset)
  offset += DatChunk.size
  chunks[chunk.type] = FilePart(file, offset, chunk.size)
  offset += chunk.size

 dend = DendChunk.unpack(chunks['DEND'])
 if crc32(FilePart(file, 0, offset - DatChunk.size - DendChunk.size)) != dend.crc:
  raise Exception('Wrong checksum')

 return chunks
