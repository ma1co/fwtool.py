"""Decrypter & parser for FDAT firmware images"""

from collections import namedtuple, OrderedDict
import io
import re
import shutil

try:
 from Cryptodome.Cipher import AES
 from Cryptodome.Hash import SHA
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Cipher import AES
 from Crypto.Hash import SHA
 from Crypto.Util.strxor import strxor

from . import constants
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
fdatHeaderMagic = b'UDTRFIRM'
fdatVersion = b'0100'

updateModeUser = b'U'
updateModeVerskip = b'O'
updateModeMinor = b'M'
updateModeProd = b'P'

luwFlagNormal = b'N'

fsModeTypeUser = b'U'
fsModeTypeProd = b'P'


class BlockCryptException(Exception):
 pass


class Crypter(object):
 def __init__(self, decryptBlockSize, encryptBlockSize):
  self._decryptBlockSize = decryptBlockSize
  self._encryptBlockSize = encryptBlockSize

 def unpackBlock(self, data):
  return data

 def packBlock(self, data):
  return data

 def decryptBlock(self, data):
  return data

 def encryptBlock(self, data):
  return data

 def _crypt(self, file, blockSize, cryptFunc):
  def generateChunks():
   file.seek(0)
   self.isFirstBlock = True
   nextData = file.read(blockSize)
   while nextData != b'':
    data = nextData
    nextData = file.read(blockSize)
    self.isLastBlock = (nextData == b'')
    yield cryptFunc(data)
    self.isFirstBlock = False
  return ChunkedFile(generateChunks)

 def decrypt(self, file):
  return self._crypt(file, self._decryptBlockSize, lambda data: self.unpackBlock(self.decryptBlock(data)))

 def encrypt(self, file):
  return self._crypt(file, self._encryptBlockSize, lambda data: self.encryptBlock(self.packBlock(data)))


class BlockCrypter(Crypter):
 def __init__(self, blockSize):
  super(BlockCrypter, self).__init__(blockSize, blockSize - 4)

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

 def packBlock(self, data):
  sizeAndEndFlag = len(data)
  if self.isLastBlock:
   sizeAndEndFlag |= 0x8000
  data = dump16le(sizeAndEndFlag) + data + b'\xff' * (self._decryptBlockSize - 4 - len(data))
  return dump16le(self._calcSum(data)) + data


class ShaCrypter(BlockCrypter):
 """Decrypts a block from a 1st gen firmware image using sha1 digests"""
 def __init__(self, key):
  super(ShaCrypter, self).__init__(1000)
  self._key = key

 def decryptBlock(self, data):
  if self.isFirstBlock:
   self._digest = self._key[:20]
  xorKey = io.BytesIO()
  while xorKey.tell() < len(data):
   self._digest = SHA.new(self._digest + self._key[20:40]).digest()
   xorKey.write(self._digest)
  return strxor(data, xorKey.getvalue())

 def encryptBlock(self, data):
  return self.decryptBlock(data)


class AesCrypter(BlockCrypter):
 """Decrypts a block from a 2nd gen firmware image using AES"""
 def __init__(self, key):
  super(AesCrypter, self).__init__(1024)
  self._cipher = AES.new(key, AES.MODE_ECB)

 def decryptBlock(self, data):
  return self._cipher.decrypt(data)

 def encryptBlock(self, data):
  return self._cipher.encrypt(data)


class DoubleAesCrypter(AesCrypter):
 """Decrypts a block from a 3rd gen firmware image using AES"""
 def __init__(self, key1, key2):
  super(DoubleAesCrypter, self).__init__(key1)
  self._cipher2 = AES.new(key2, AES.MODE_ECB)

 def decryptBlock(self, data):
  decrypted = super(DoubleAesCrypter, self).decryptBlock(data)
  doubleDecrypted = self._cipher2.decrypt(decrypted)
  if self.isFirstBlock:
   return decrypted[:512] + doubleDecrypted[512:]
  else:
   return doubleDecrypted

 def encryptBlock(self, data):
  encrypted = self._cipher2.encrypt(data)
  if self.isFirstBlock:
   encrypted = data[:512] + encrypted[512:]
  return super(DoubleAesCrypter, self).encryptBlock(encrypted)


class AesCbcCrypter(AesCrypter):
 """Decrypts a block from a 4th gen firmware image using AES CBC"""
 def __init__(self, key1, key2):
  super(AesCbcCrypter, self).__init__(key1)
  self._key = key2

 def decryptBlock(self, data):
  if self.isFirstBlock:
   self._cipher2 = AES.new(self._key, AES.MODE_CBC, self._iv)
   return super(AesCbcCrypter, self).decryptBlock(data[:512]) + self._cipher2.decrypt(data[512:])
  else:
   return self._cipher2.decrypt(data)

 def decrypt(self, file):
  file.seek(-0x110, 2)
  size = file.tell()
  self._iv = file.read(0x10)
  file = FilePart(file, 0, size)
  return super(AesCbcCrypter, self).decrypt(file)

 def encrypt(self, file):
  raise Exception('Encryption not supported')


_crypters = OrderedDict([
 ('CXD4105',      lambda: ShaCrypter(constants.key_cxd4105)),
 ('MB8AC102',     lambda: ShaCrypter(constants.key_mb8ac102)),
 ('CXD4115',      lambda: ShaCrypter(constants.key_cxd4115)),
 ('CXD4115_ilc',  lambda: ShaCrypter(constants.key_cxd4115_ilc)),
 ('CXD4120',      lambda: ShaCrypter(constants.key_cxd4120)),
 ('CXD4120_pro',  lambda: ShaCrypter(constants.key_cxd4120_pro)),
 ('CXD4132',      lambda: AesCrypter(constants.key_cxd4132)),
 ('CXD90014',     lambda: DoubleAesCrypter(constants.key_aes, constants.key_cxd90014)),
 ('CXD90045',     lambda: AesCbcCrypter(constants.key_aes, constants.key_cxd90045)),
])


def modelIsAccessory(model):
 return model & 0xff0000 == 0xa00000


def isFdat(file):
 """Returns true if the file provided is a fdat file"""
 header = FdatHeader.unpack(file)
 return header and header.magic == fdatHeaderMagic and header.fileSystemHeaders.endswith(4*b'\0')


def decryptFdat(file):
 """Decrypts an encrypted FDAT file"""
 for crypterName, crypter in _crypters.items():
  try:
   fdatFile = crypter().decrypt(file)
   if isFdat(fdatFile):
    fdatFile.seek(0)
    return crypterName, fdatFile
  except BlockCryptException:
   pass
 raise Exception('No decrypter found')


def encryptFdat(file, crypterName):
 """Encrypts a FDAT file"""
 return _crypters[crypterName]().encrypt(file)


def _calcCrc(file):
 return crc32(FilePart(file, 12, FdatHeader.size - 12))


def readFdat(file):
 """Reads a decrypted FDAT file and returns its contents"""
 header = FdatHeader.unpack(file)

 if header.magic != fdatHeaderMagic:
  raise Exception('Wrong magic')

 if header.version != fdatVersion:
  raise Exception('Wrong version')

 if _calcCrc(file) != header.checksum:
  raise Exception('Wrong checksum')

 if header.modeType != updateModeUser:
  raise Exception('Unsupported mode')

 if header.luwFlag != luwFlagNormal:
  raise Exception('Unsupported LUW flag')

 fileSystem = None
 for i in range(0, len(header.fileSystemHeaders), FdatFileSystemHeader.size):
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


def writeFdat(fdat, outFile):
 """Writes a non-encrypted FDAT file"""
 outFile.seek(0)
 outFile.write(b'\0' * FdatHeader.size)
 fsOffset = FdatHeader.size

 fdat.fs.seek(0)
 shutil.copyfileobj(fdat.fs, outFile)
 firmwareOffset = outFile.tell()

 fdat.firmware.seek(0)
 shutil.copyfileobj(fdat.firmware, outFile)
 endOffset = outFile.tell()

 version = re.match('^(\d)\.(\d{2})$', fdat.version)
 if not version:
  raise Exception('Cannot parse version string')

 if modelIsAccessory(fdat.model) != fdat.isAccessory:
  raise Exception('Wrong accessory flag')

 outFile.seek(0)
 outFile.write(FdatHeader.pack(
  magic = fdatHeaderMagic,
  checksum = 0,
  version = fdatVersion,
  modeType = updateModeUser,
  luwFlag = luwFlagNormal,
  versionMinor = int(version.group(2), 16),
  versionMajor = int(version.group(1), 16),
  model = fdat.model,
  region = fdat.region,
  firmwareOffset = firmwareOffset,
  firmwareSize = endOffset - firmwareOffset,
  numFileSystems = 2,
  fileSystemHeaders = FdatFileSystemHeader.pack(modeType=fsModeTypeUser, offset=fsOffset, size=firmwareOffset-fsOffset)
                    + FdatFileSystemHeader.pack(modeType=fsModeTypeProd, offset=fsOffset, size=0)
                    + b'\0' * ((maxNumFileSystems-2) * FdatFileSystemHeader.size),
 ))

 crc = _calcCrc(outFile)
 outFile.seek(8)
 outFile.write(dump32le(crc))
