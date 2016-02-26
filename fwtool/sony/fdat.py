"""Decrypter & parser for FDAT firmware images"""

from collections import namedtuple
import hashlib
import io
import struct

import constants
from ..io import FilePart
from ..util import *

FdatFile = namedtuple('FdatFile', 'tar, img')

FdatEncryptionHeader = Struct('FdatEncryptionHeader', [
 ('checksum', Struct.INT16),
 ('size', Struct.INT16),
])

FdatHeader = Struct('FdatHeader', [
 ('magic', Struct.STR % 8),
 ('checksum', Struct.INT32),
 ('...', 36),
 ('tarOffset', Struct.INT32),
 ('tarSize', Struct.INT32),
 ('...', 12),
 ('imgOffset', Struct.INT32),
 ('imgSize', Struct.INT32),
 ('...', 432),
 ('end', Struct.INT32),
])
fdatHeaderMagic = 'UDTRFIRM'

class Decrypter:
 def __init__(self, file, blockSize):
  file.seek(0)
  self.file = file
  self.blockSize = blockSize

 def __iter__(self):
  return self

 def next(self):
  data = self.file.read(self.blockSize)
  if data == '':
   raise StopIteration
  return self.decrypt(data)

class Gen1Decrypter(Decrypter):
 """Decrypts a block from a 1st gen firmware image using sha1 digests"""
 def __init__(self, file):
  self.digest = constants.shaKey1
  Decrypter.__init__(self, file, 1000)

 def _fastXor(self, xs, ys):
  """Fast xor between two strings. len(xs) must be a multiple of 8, ys must be at least as long as xs"""
  fmt = str(len(xs) / 8) + 'Q'
  return struct.pack(fmt, *[x ^ y for x, y in zip(struct.unpack(fmt, xs), struct.unpack(fmt, ys[:len(xs)]))])

 def decrypt(self, data):
  xorKey = io.BytesIO()
  while xorKey.tell() < len(data):
   self.digest = hashlib.sha1(self.digest + constants.shaKey2).digest()
   xorKey.write(self.digest)
  return self._fastXor(data, xorKey.getvalue())

class Gen2Decrypter(Decrypter):
 """Decrypts a block from a 2nd gen firmware image using AES"""
 def __init__(self, file):
  Decrypter.__init__(self, file, 1024)

 def decrypt(self, data):
  return constants.cipherV2.decrypt(data)

class Gen3Decrypter(Gen2Decrypter):
 """Decrypts a block from a 3rd gen firmware image using AES"""
 def __init__(self, file):
  self.isFirstBlock = True
  Gen2Decrypter.__init__(self, file)

 def decrypt(self, data):
  decrypt = Gen2Decrypter.decrypt(self, data)
  newDecrypt = constants.cipherV3.decrypt(decrypt)
  if self.isFirstBlock:
   self.isFirstBlock = False
   return decrypt[:512] + newDecrypt[512:]
  else:
   return newDecrypt

def isFdat(file):
 """Returns true if the file provided is a fdat file"""
 header = FdatHeader.unpack(file)
 return header and header.magic == fdatHeaderMagic

def decryptFdat(srcFile, dstFile):
 """Decrypts an encrypted FDAT file"""
 decrypters = [Gen1Decrypter, Gen2Decrypter, Gen3Decrypter]

 for decrypter in decrypters:
  fdatHeader = FdatHeader.unpack(next(decrypter(srcFile)), FdatEncryptionHeader.size)
  if fdatHeader.magic == fdatHeaderMagic and fdatHeader.end == 0:
   for block in decrypter(srcFile):
    header = FdatEncryptionHeader.unpack(block)
    if sum(parse16leArr(block[2:])) & 0xffff != header.checksum:
     raise Exception('Wrong checksum')
    dstFile.write(block[FdatEncryptionHeader.size:FdatEncryptionHeader.size+header.size])
   break
 else:
  raise Exception('No decrypter found')

def readFdat(file):
 """Reads a decrypted FDAT file and returns its contents"""
 header = FdatHeader.unpack(file)

 if header.magic != fdatHeaderMagic:
  raise Exception('Wrong magic')

 if crc32(FilePart(file, 12, FdatHeader.size - 12)) != header.checksum:
  raise Exception('Wrong checksum')

 return FdatFile(
  tar = FilePart(file, header.tarOffset, header.tarSize),
  img = FilePart(file, header.imgOffset, header.imgSize),
 )
