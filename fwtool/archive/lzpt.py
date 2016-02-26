"""A decoder for LZPT compressed image files"""

import io
from stat import *

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

def isLzpt(file):
 """Checks if the LZTP header is present"""
 header = LzptHeader.unpack(file)
 return header and header.magic == lzptHeaderMagic

def readLzpt(file):
 """Decodes an LZTP image and returns its contents"""
 header = LzptHeader.unpack(file)

 if header.magic != lzptHeaderMagic:
  raise Exception('Wrong magic')

 tocEntries = [LzptTocEntry.unpack(file, header.tocOffset + offset) for offset in xrange(0, header.tocSize, LzptTocEntry.size)]

 def extractTo(dstFile):
  for entry in tocEntries:
   file.seek(entry.offset)
   block = io.BytesIO(file.read(entry.size))

   pos = dstFile.tell()
   while dstFile.tell() < pos + 2 ** header.blockSize:
    dstFile.write(lz77.inflateLz77(block))

 yield UnixFile(
  path = '',
  size = -1,
  mtime = 0,
  mode = S_IFREG,
  uid = 0,
  gid = 0,
  extractTo = extractTo,
 )
