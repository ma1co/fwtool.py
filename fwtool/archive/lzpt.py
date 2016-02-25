"""A decoder for LZPT compressed image files"""

import math
from stat import *
from StringIO import StringIO

from . import *
from ..util import *

LzptHeader = Struct('LzptHeader', [
 ('magic', Struct.STR % 4),
 ('blockSize', Struct.INT32),
 ('tocOffset', Struct.INT32),
 ('tocSize', Struct.INT32),
])
lzptHeaderMagic = 'TPZL'

LzptTocEntry = Struct('LzptTocEntry', [
 ('offset', Struct.INT32),
 ('size', Struct.INT32),
])

def decodeLz77(data):
 """Decodes LZ77 compressed data"""
 if ord(data[0]) == 0x0f:
  l = ord(data[2]) | ord(data[3]) << 8
  return 4+l, data[4:4+l]
 elif ord(data[0]) == 0xf0:
  out = ''
  offset = 1
  lengths = range(3, 17) + [32, 64]

  while True:
   flags = ord(data[offset])
   offset += 1

   for i in xrange(8):
    if (flags >> i) & 0x1:
     l = lengths[ord(data[offset]) >> 4]
     bd = (ord(data[offset]) & 0xf) << 8 | ord(data[offset + 1])
     offset += 2

     if bd == 0:
      return offset, out

     d = out[-bd:]
     d *= int(math.ceil(l * 1. / len(d)))
     out += d[:l]
    else:
     out += data[offset]
     offset += 1
 else:
  raise Exception('Unknown type')

def isLzpt(data):
 """Checks if the LZTP header is present"""
 return len(data) >= LzptHeader.size and LzptHeader.unpack(data).magic == lzptHeaderMagic

def readLzpt(data):
 """Decodes an LZTP image and returns its contents"""
 header = LzptHeader.unpack(data)

 if header.magic != lzptHeaderMagic:
  raise Exception('Wrong magic')

 out = StringIO()
 for offset in xrange(header.tocOffset, header.tocOffset+header.tocSize, LzptTocEntry.size):
  tocEntry = LzptTocEntry.unpack(data, offset)
  block = memoryview(data)[tocEntry.offset:tocEntry.offset+tocEntry.size]

  pos = out.tell()
  while out.tell() < pos + 2 ** header.blockSize:
   l, decoded = decodeLz77(block.tobytes())
   out.write(decoded)
   block = block[l:]

 contents = out.getvalue()
 return {'': UnixFile(
  size = len(contents),
  mtime = 0,
  mode = S_IFREG,
  uid = 0,
  gid = 0,
  contents = contents,
 )}
