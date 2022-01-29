import io

try:
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Util.strxor import strxor

from ..util import *

def cryptXor55(a, data):
 n = 55
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
