"""LZ77 decompressor"""
# Kernel source: lib/lz77/lz77_inflate.c

_lengths = list(range(3, 17)) + [32, 64]

def _makeFlagTable():
 """For each flag byte, precompute the sequence of tokens: a positive number n stands for a run of n
 literal bytes, 0 stands for a back reference"""
 table = []
 for flags in range(256):
  tokens = []
  run = 0
  for i in range(8):
   if (flags >> i) & 0x1:
    if run:
     tokens.append(run)
     run = 0
    tokens.append(0)
   else:
    run += 1
  if run:
   tokens.append(run)
  table.append(tokens)
 return table

_flagTable = _makeFlagTable()

def inflateLz77Buffer(data, offset=0):
 """Decodes LZ77 compressed data starting at the given offset of a buffer.
 Returns the decoded data and the offset after the compressed block."""
 if not isinstance(data, bytearray):
  data = bytearray(data)
 type = data[offset]

 if type == 0x0f:
  l = data[offset + 2] | data[offset + 3] << 8
  start = offset + 4
  return bytes(data[start:start+l]), min(start + l, len(data))
 elif type == 0xf0:
  out = bytearray()
  pos = offset + 1
  lengths = _lengths
  flagTable = _flagTable

  while True:
   tokens = flagTable[data[pos]]
   pos += 1

   for n in tokens:
    if n:
     # run of literal bytes
     out += data[pos:pos+n]
     pos += n
    else:
     # back reference
     b0 = data[pos]
     bd = (b0 & 0xf) << 8 | data[pos + 1]
     pos += 2

     if bd == 0:
      return bytes(out), pos

     l = lengths[b0 >> 4]
     size = len(out)
     if l <= bd <= size:
      start = size - bd
      out += out[start:start+l]
     else:
      d = out[-bd:]
      d *= l // len(d) + 1
      out += d[:l]
 else:
  raise Exception('Unknown type')

def inflateLz77(file):
 """Decodes LZ77 compressed data from a file and leaves the file positioned after the compressed block"""
 start = file.tell()
 out, end = inflateLz77Buffer(file.read())
 file.seek(start + end)
 return out
