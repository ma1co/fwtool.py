"""A decoder for LZPT compressed image files"""

from stat import *
from StringIO import StringIO

from . import *
from .. import lz77
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
   l, decoded = lz77.inflateLz77(block.tobytes())
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
