"""Decrypter & parser for FDAT firmware images"""

from collections import namedtuple, OrderedDict
from Crypto.Cipher import AES
from Crypto.Hash import SHA
from Crypto.Util.strxor import strxor
import io
import struct

import constants
from ..io import *
from ..util import *

FdatFile = namedtuple('FdatFile', 'model, region, version, isAccessory, firmware, fs')

FdatFileSystemHeader = Struct('FdatFileSystemHeader', [
 ('modeType', Struct.STR % 1),
 ('...', 3),
 ('offset', Struct.INT32),
 ('size', Struct.INT32),
 ('...', 4),
])
maxNumFileSystems = 28

FdatHeader = Struct('FdatHeader', [
 ('magic', Struct.STR % 8),
 ('checksum', Struct.INT32),
 ('version', Struct.STR % 4),

 ('modeType', Struct.STR % 1),
 ('...', 3),
 ('luwFlag', Struct.STR % 1),
 ('...', 3),
 ('...', 8),

 ('versionMinor', Struct.INT8),
 ('versionMajor', Struct.INT8),
 ('...', 2),
 ('model', Struct.INT32),
 ('region', Struct.INT32),
 ('...', 4),

 ('firmwareOffset', Struct.INT32),
 ('firmwareSize', Struct.INT32),
 ('numFileSystems', Struct.INT32),
 ('...', 4),

 ('fileSystemHeaders', Struct.STR % (maxNumFileSystems * FdatFileSystemHeader.size))
])
fdatHeaderMagic = 'UDTRFIRM'
fdatVersion = '0100'

updateModeUser = 'U'
updateModeVerskip = 'O'
updateModeMinor = 'M'
updateModeProd = 'P'

luwFlagNormal = 'N'

fsModeTypeUser = 'U'
fsModeTypeProd = 'P'


class BlockCryptException(Exception):
 pass


class Crypter(object):
 def __init__(self, decryptBlockSize):
  self._decryptBlockSize = decryptBlockSize

 def unpackBlock(self, data):
  return data

 def decryptBlock(self, data):
  return data

 def _crypt(self, file, blockSize, cryptFunc):
  def generateChunks():
   file.seek(0)
   self.isFirstBlock = True
   nextData = file.read(blockSize)
   while nextData != '':
    data = nextData
    nextData = file.read(blockSize)
    self.isLastBlock = (nextData == '')
    yield cryptFunc(data)
    self.isFirstBlock = False
  return ChunkedFile(generateChunks)

 def decrypt(self, file):
  return self._crypt(file, self._decryptBlockSize, lambda data: self.unpackBlock(self.decryptBlock(data)))


class BlockCrypter(Crypter):
 def __init__(self, blockSize):
  super(BlockCrypter, self).__init__(blockSize)

 def _calcSum(self, data):
  return sum(parse16leArr(data)) & 0xffff

 def unpackBlock(self, data):
  checksum = parse16le(data[:2])
  sizeAndEndFlag = parse16le(data[2:4])
  size = sizeAndEndFlag & 0x7fff
  endFlag = (sizeAndEndFlag & 0x8000) != 0
  if self._calcSum(data[2:]) != checksum:
   raise BlockCryptException('Wrong checksum')
  if endFlag != self.isLastBlock:
   raise BlockCryptException('Wrong last block flag')
  return data[4:4+size]


class ShaCrypter(BlockCrypter):
 """Decrypts a block from a 1st gen firmware image using sha1 digests"""
 def __init__(self, key1, key2):
  super(ShaCrypter, self).__init__(1000)
  self._key1 = key1
  self._key2 = key2

 def decryptBlock(self, data):
  if self.isFirstBlock:
   self._digest = self._key1
  xorKey = io.BytesIO()
  while xorKey.tell() < len(data):
   self._digest = SHA.new(self._digest + self._key2).digest()
   xorKey.write(self._digest)
  return strxor(data, xorKey.getvalue())


class AesCrypter(BlockCrypter):
 """Decrypts a block from a 2nd gen firmware image using AES"""
 def __init__(self, key):
  super(AesCrypter, self).__init__(1024)
  self._cipher = AES.AESCipher(key, AES.MODE_ECB)

 def decryptBlock(self, data):
  return self._cipher.decrypt(data)


class DoubleAesCrypter(AesCrypter):
 """Decrypts a block from a 3rd gen firmware image using AES"""
 def __init__(self, key1, key2):
  super(DoubleAesCrypter, self).__init__(key1)
  self._cipher2 = AES.AESCipher(key2, AES.MODE_ECB)

 def decryptBlock(self, data):
  decrypted = super(DoubleAesCrypter, self).decryptBlock(data)
  doubleDecrypted = self._cipher2.decrypt(decrypted)
  if self.isFirstBlock:
   return decrypted[:512] + doubleDecrypted[512:]
  else:
   return doubleDecrypted


_crypters = OrderedDict([
 ('gen1', lambda: ShaCrypter(constants.shaKey1, constants.shaKey2)),
 ('gen2', lambda: AesCrypter(constants.aesKeyV2)),
 ('gen3', lambda: DoubleAesCrypter(constants.aesKeyV2, constants.aesKeyV3)),
])


def modelIsAccessory(model):
 return model & 0xff0000 == 0xa00000


def isFdat(file):
 """Returns true if the file provided is a fdat file"""
 header = FdatHeader.unpack(file)
 return header and header.magic == fdatHeaderMagic and header.fileSystemHeaders.endswith(4*'\x00')


def decryptFdat(file):
 """Decrypts an encrypted FDAT file"""
 for crypterName, crypter in _crypters.iteritems():
  try:
   fdatFile = crypter().decrypt(file)
   if isFdat(fdatFile):
    fdatFile.seek(0)
    return crypterName, fdatFile
  except BlockCryptException:
   pass
 raise Exception('No decrypter found')


def readFdat(file):
 """Reads a decrypted FDAT file and returns its contents"""
 header = FdatHeader.unpack(file)

 if header.magic != fdatHeaderMagic:
  raise Exception('Wrong magic')

 if header.version != fdatVersion:
  raise Exception('Wrong version')

 if crc32(FilePart(file, 12, FdatHeader.size - 12)) != header.checksum:
  raise Exception('Wrong checksum')

 if header.modeType != updateModeUser:
  raise Exception('Unsupported mode')

 if header.luwFlag != luwFlagNormal:
  raise Exception('Unsupported LUW flag')

 fileSystem = None
 for i in xrange(0, len(header.fileSystemHeaders), FdatFileSystemHeader.size):
  fs = FdatFileSystemHeader.unpack(header.fileSystemHeaders, i)
  if fs.modeType == fsModeTypeUser:
   fileSystem = fs
   break
 if not fileSystem:
  raise Exception('No file system found')

 return FdatFile(
  model = header.model,
  region = header.region,
  version = '%x.%02x' % (header.versionMajor, header.versionMinor),
  isAccessory = modelIsAccessory(header.model),
  firmware = FilePart(file, header.firmwareOffset, header.firmwareSize),
  fs = FilePart(file, fileSystem.offset, fileSystem.size),
 )
