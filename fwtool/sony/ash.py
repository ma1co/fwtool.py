from collections import namedtuple
import io

from .xor55 import *
from ..util import *

AshFile = namedtuple('AshFile', 'model, region, version, firmware')

AshHeader = Struct('AshHeader', [
 ('magic', Struct.STR % 8),
 ('model', Struct.STR % 4),
 ('region', Struct.STR % 4),
 ('checksum', Struct.INT32),
 ('...', 4),
 ('size', Struct.STR % 8),
 ('version', Struct.INT16),
 ('...', 30),
], Struct.BIG_ENDIAN)
ashHeaderMagic = b'CX0900AP'

def _decryptLut(data):
 lut = bytes(b * b * b % 253 if b < 253 else b for b in range(256))
 return b''.join(lut[b:b+1] for b in data)

def _decryptXor(data):
 return cryptXor55(0x12345678, data)

def _findDecryptFunc(file):
 file.seek(0)
 data = file.read(AshHeader.size)
 for f in [_decryptLut, _decryptXor]:
  header = AshHeader.unpack(f(data))
  if header and header.magic == ashHeaderMagic:
   return f

def isAsh(file):
 return _findDecryptFunc(file) is not None

def readAsh(file):
 decrypt = _findDecryptFunc(file)
 if decrypt is None:
  raise Exception('Cannot decrypt')

 file.seek(0)
 data = decrypt(file.read())
 header = AshHeader.unpack(data)

 if header.magic != ashHeaderMagic:
  raise Exception('Wrong magic')
 if (sum(data[AshHeader.size:]) & 0xffffffff) != header.checksum:
  raise Exception('Wrong checksum')

 return AshFile(int(header.model), int(header.region, 16), '%d.00' % header.version, io.BytesIO(data))
