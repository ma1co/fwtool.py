from collections import namedtuple
import io

try:
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Util.strxor import strxor

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
 n = 55
 a = 0x12345678
 b = 1
 step = lambda a, b: a - b + (1000000000 if a < b else 0)
 state = [0] * (n - 1) + [a]
 for i in range(1, n):
  state[(21 * i % n) - 1] = b
  a, b = b, step(a, b)
 mask = io.BytesIO()
 while mask.tell() < 12 * n + len(data):
  for i in range(n):
   state[i] = step(state[i], state[i - 24])
   mask.write(dump32be(state[i]))
 return strxor(data, mask.getvalue()[12*n:12*n+len(data)])

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
