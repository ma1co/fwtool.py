"""Decrypter & parser for FDAT firmware images"""

import hashlib
import math
from StringIO import StringIO
import struct

import constants
from ..util import *

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

def _fastXor(xs, ys):
 """Fast xor between two strings. len(xs) must be a multiple of 8, ys must be at least as long as xs"""
 fmt = str(len(xs) / 8) + 'Q'
 return struct.pack(fmt, *[x ^ y for x, y in zip(struct.unpack(fmt, xs), struct.unpack(fmt, ys[:len(xs)]))])

def decryptBlockV1(data, i):
 """Decrypts a block from a 1st gen firmware image using sha1 digests"""
 global _digest
 if i == 0:
  _digest = constants.shaKey1
 xorKey = StringIO()
 for i in range(int(math.ceil(len(data) / 20.))):
  _digest = hashlib.sha1(_digest + constants.shaKey2).digest()
  xorKey.write(_digest)
 return _fastXor(data, xorKey.getvalue())

def decryptBlockV2(data, i):
 """Decrypts a block from a 2nd gen firmware image using AES"""
 return constants.cipherV2.decrypt(data)

def decryptBlockV3(data, i):
 """Decrypts a block from a 3rd gen firmware image using AES"""
 decrypt = decryptBlockV2(data, i)
 newDecrypt = constants.cipherV3.decrypt(decrypt)
 return decrypt[:512] + newDecrypt[512:] if i == 0 else newDecrypt

def _decrypt(data, func, l):
 """Decrypts all blocks in a firmware image using the provided decryption function"""
 fdat = StringIO()
 for i in xrange(0, len(data), l):
  decrypt = func(data[i:i+l], i)
  header = FdatEncryptionHeader.unpack(decrypt)
  if sum(parse16leArr(decrypt[2:])) & 0xffff != header.checksum:
   raise Exception('Wrong checksum')
  fdat.write(decrypt[FdatEncryptionHeader.size:FdatEncryptionHeader.size+header.size])
 return fdat.getvalue()

def isFdat(data):
 """Returns true if the data provided is a fdat file"""
 return len(data) >= FdatHeader.size and FdatHeader.unpack(data).magic == fdatHeaderMagic

def decryptFdat(data):
 """Takes the encrypted FDAT contents, decrypts the image and returns an Fdat instance"""
 funcs = [
  (decryptBlockV1, constants.blockSizeV1),
  (decryptBlockV2, constants.blockSizeV2),
  (decryptBlockV3, constants.blockSizeV3)
 ]

 for func, l in funcs:
  header = FdatHeader.unpack(func(data[:l], 0), 4)
  if header.magic == fdatHeaderMagic and header.end == 0:
   return Fdat(_decrypt(data, func, l))

 raise Exception('No decrypter found')

class Fdat:
 """A class representing an FDAT image"""
 def __init__(self, data):
  self.data = data
  self.header = FdatHeader.unpack(data)

  if self.header.magic != fdatHeaderMagic:
   raise Exception('Wrong magic')

  if crc32(self.data[12:FdatHeader.size]) != self.header.checksum:
   raise Exception('Wrong checksum')

 def getTar(self):
  """Returns the contents of the main .tar file"""
  return memoryview(self.data)[self.header.tarOffset:self.header.tarOffset+self.header.tarSize]

 def getImg(self):
  """Returns the contents of the updater image file"""
  return memoryview(self.data)[self.header.imgOffset:self.header.imgOffset+self.header.imgSize]
