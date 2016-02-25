"""LZ77 decompressor"""

import math

def inflateLz77(data):
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
