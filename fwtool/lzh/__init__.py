"""Parser for LZH archives"""

import time

from ..io import *
from ..util import *

LzhFile = namedtuple('ZipFile', 'size, mtime, contents')

LzhHeader = Struct('LzhHeader', [
 ('size', Struct.INT8),
 ('checksum', Struct.INT8),
 ('method', Struct.STR % 5),
 ('compressedSize', Struct.INT32),
 ('uncompressedSize', Struct.INT32),
 ('date', Struct.INT32),
 ('attr', Struct.INT8),
 ('level', Struct.INT8),
])
lzhMethod = b'-lh0-'

def isLzh(file):
 header = LzhHeader.unpack(file)
 return header and header.method == lzhMethod

def readLzh(file):
 header = LzhHeader.unpack(file)

 if header.method != lzhMethod:
  raise Exception('Only uncompressed LZH archives are supported')

 headerSize = header.size
 if header.level == 2:
  headerSize += header.checksum << 8

 mtime = header.date
 if header.level != 2:
  mtime = time.mktime((1980 + (header.date >> 25), (header.date >> 21) & 0xf, (header.date >> 16) & 0x1f, (header.date >> 11) & 0x1f, (header.date >> 5) & 0x3f, (header.date & 0x1f) * 2, -1, -1, -1))

 return LzhFile(
  size=header.uncompressedSize,
  mtime=mtime,
  contents=FilePart(file, headerSize, header.uncompressedSize)
 )
