"""Some utility functions to unpack integers"""

import binascii
import struct

from collections import namedtuple

def parse32be(data):
 return struct.unpack('>I', data)[0]

def parse32le(data):
 return struct.unpack('<I', data)[0]

def parse16be(data):
 return struct.unpack('>H', data)[0]

def parse16le(data):
 return struct.unpack('<H', data)[0]

def parse16leArr(data):
 return struct.unpack('<%sH' % str(len(data) / 2), data)

def crc32(data):
 return binascii.crc32(data) & 0xffffffff

class Struct:
 LITTLE_ENDIAN = '<'
 BIG_ENDIAN = '>'
 PADDING = '%dx'
 CHAR = 'c'
 STR = '%ds'
 INT64 = 'Q'
 INT32 = 'I'
 INT16 = 'H'
 INT8 = 'B'

 def __init__(self, name, fields, byteorder=LITTLE_ENDIAN):
  self.tuple = namedtuple(name, (n for n, fmt in fields if not isinstance(fmt, int)))
  self.format = byteorder + ''.join(self.PADDING % fmt if isinstance(fmt, int) else fmt for n, fmt in fields)
  self.size = struct.calcsize(self.format)

 def unpack(self, data, offset = 0):
  return self.tuple._make(struct.unpack_from(self.format, data, offset))
