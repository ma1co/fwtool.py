"""Decrypter & parser for FDAT firmware images"""

import hashlib
import math
from StringIO import StringIO
import struct

import constants
from ..util import *

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
  checksum = parse16le(decrypt[:2])
  length = parse16le(decrypt[2:4]) & 0x0fff
  if sum(parse16leArr(decrypt[2:])) & 0xffff != checksum:
   raise Exception('Wrong checksum')
  fdat.write(decrypt[4:4+length])
 return fdat.getvalue()

def decryptFdat(data):
 """Takes the encrypted FDAT contents, decrypts the image and returns an Fdat instance"""
 funcs = [
  (decryptBlockV1, constants.blockSizeV1),
  (decryptBlockV2, constants.blockSizeV2),
  (decryptBlockV3, constants.blockSizeV3)
 ]

 for func, l in funcs:
  decrypt = func(data[:l], 0)[4:]
  if decrypt[:8] == constants.fdatHeader and decrypt[508:512] == 4*'\x00':
   return Fdat(_decrypt(data, func, l))

 raise Exception('No decrypter found')

class Fdat:
 """A class representing an FDAT image"""
 def __init__(self, data):
  self.data = data

  if self.data[:8] != constants.fdatHeader:
   raise Exception('Wrong header')

  if crc32(self.data[12:512]) != parse32le(self.data[8:12]):
   raise Exception('Wrong checksum')

 def getTar(self):
  """Returns the contents of the main .tar file"""
  offset = parse32le(self.data[48:52])
  length = parse32le(self.data[52:56])
  return self.data[offset:offset+length]

 def getImg(self):
  """Returns the contents of the updater image file"""
  offset = parse32le(self.data[68:72])
  length = parse32le(self.data[72:76])
  return self.data[offset:offset+length]
