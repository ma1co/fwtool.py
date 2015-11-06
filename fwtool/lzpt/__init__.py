"""A decoder for LZPT compressed image files"""

import math
from StringIO import StringIO

from ..util import *

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
 return data[:4] == 'TPZL'

def readLzpt(data):
 """Decodes an LZTP image and returns its contents"""
 if not isLzpt(data):
  raise Exception('Wrong header')

 blockLen = 2 ** parse32le(data[4:8])
 tocOffset = parse32le(data[8:12])
 tocLen = parse32le(data[12:16])

 out = StringIO()
 for i in xrange(tocOffset, tocOffset+tocLen, 8):
  offset = parse32le(data[i:i+4])
  length = parse32le(data[i+4:i+8])
  block = memoryview(data)[offset:offset+length]

  pos = out.tell()
  while out.tell() < pos + blockLen:
   l, decoded = decodeLz77(block.tobytes())
   out.write(decoded)
   block = block[l:]

 return out.getvalue()
