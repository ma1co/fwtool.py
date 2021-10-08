from collections import namedtuple
import io

from ..util import *

AshFile = namedtuple('AshFile', 'model, region, version, firmware')

AshHeader = Struct('AshHeader', [
 ('magic', Struct.STR % 8),
 ('model', Struct.STR % 4),
 ('region', Struct.STR % 4),
 ('checksum', Struct.INT32),
 ('...', 12),
 ('versionMinor', Struct.INT8),
 ('versionMajor', Struct.INT8),
 ('...', 30),
], Struct.BIG_ENDIAN)
ashHeaderMagic = b'CX0900AP'

def _decryptByte(b):
 if b < 253:
  b = b * b * b % 253
 return b

def _decrypt(data):
 lut = bytes(_decryptByte(b) for b in range(256))
 return b''.join(lut[b:b+1] for b in data)

def isAsh(file):
 file.seek(0)
 header = AshHeader.unpack(_decrypt(file.read(AshHeader.size)))
 return header and header.magic == ashHeaderMagic

def readAsh(file):
 file.seek(0)
 data = _decrypt(file.read())
 header = AshHeader.unpack(data)

 if header.magic != ashHeaderMagic:
  raise Exception('Wrong magic')
 if (sum(data[AshHeader.size:]) & 0xffffffff) != header.checksum:
  raise Exception('Wrong checksum')

 return AshFile(int(header.model), int(header.region, 16), '%x.%02x' % (header.versionMajor, header.versionMinor), io.BytesIO(data))
