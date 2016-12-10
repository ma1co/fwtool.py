"""LZ77 decompressor"""
# Kernel source: lib/lz77/lz77_inflate.c

def inflateLz77(file):
 """Decodes LZ77 compressed data"""
 type = ord(file.read(1))

 if type == 0x0f:
  file.read(1)
  data = file.read(2)
  l = ord(data[0:1]) | ord(data[1:2]) << 8
  return file.read(l)
 elif type == 0xf0:
  out = b''
  lengths = list(range(3, 17)) + [32, 64]

  while True:
   flags = ord(file.read(1))

   if flags == 0:
    # special case to improve performance
    out += file.read(8)
   else:
    for i in range(8):
     if (flags >> i) & 0x1:
      data = file.read(2)
      l = lengths[ord(data[0:1]) >> 4]
      bd = (ord(data[0:1]) & 0xf) << 8 | ord(data[1:2])

      if bd == 0:
       return out

      d = out[-bd:]
      d *= l // len(d) + 1
      out += d[:l]
     else:
      out += file.read(1)
 else:
  raise Exception('Unknown type')
