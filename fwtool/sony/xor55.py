import io

try:
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Util.strxor import strxor

from ..util import *

def _step(a, b):
 c = a - b
 if c & 0x80000000:
  c += 1000000000
 return c & 0xffffffff

def cryptXor55(a, data, little=False):
 dump32 = dump32le if little else dump32be
 n = 55
 b = 1
 state = [0] * (n - 1) + [a]
 for i in range(1, n):
  state[(21 * i % n) - 1] = b
  a, b = b, _step(a, b)
 mask = io.BytesIO()
 while mask.tell() < 12 * n + len(data):
  for i in range(n):
   state[i] = _step(state[i], state[i - 24])
   mask.write(dump32(state[i]))
 return strxor(data, mask.getvalue()[12*n:12*n+len(data)])
