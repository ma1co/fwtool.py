"""Some utility functions to unpack integers"""

import binascii
import struct

from collections import namedtuple

def parse64be(data):
 return struct.unpack('>Q', data)[0]

def dump64be(value):
 return struct.pack('>Q', value)

def parse64le(data):
 return struct.unpack('<Q', data)[0]

def dump64le(value):
 return struct.pack('<Q', value)

def parse32be(data):
 return struct.unpack('>I', data)[0]

def dump32be(value):
 return struct.pack('>I', value)

def parse32le(data):
 return struct.unpack('<I', data)[0]

def dump32le(value):
 return struct.pack('<I', value)

def parse16be(data):
 return struct.unpack('>H', data)[0]

def dump16be(value):
 return struct.pack('>H', value)

def parse16le(data):
 return struct.unpack('<H', data)[0]

def dump16le(value):
 return struct.pack('<H', value)

def parse16leArr(data):
 return struct.unpack('<%sH' % str(len(data) / 2), data)

def parse8(data):
 return ord(data)

def dump8(value):
 return chr(value)

def crc32(*files):
 crc = 0
 for file in files:
  for chunk in iter(lambda: file.read(4096), ''):
   crc = binascii.crc32(chunk, crc)
 return crc & 0xffffffff

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
  if isinstance(data, basestring):
   data = data[offset:offset+self.size]
  else:
   data.seek(offset)
   data = data.read(self.size)
  if len(data) < self.size:
   return None
  return self.tuple._make(struct.unpack_from(self.format, data))

 def pack(self, **kwargs):
  return struct.pack(self.format, *self.tuple(**kwargs))
