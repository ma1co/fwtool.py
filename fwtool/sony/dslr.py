from collections import namedtuple
import io

from .xor55 import *
from ..io import *
from ..util import *

DslrFirmwareFile = namedtuple('DslrFirmwareFile', 'model, version, files')

DslrFirmwareHeader = Struct('DslrFirmwareHeader', [
 ('magic', Struct.STR % 8),
 ('model', Struct.STR % 4),
 ('version', Struct.STR % 2),
 ('nFiles', Struct.INT8),
 ('...', 1),
 ('checksum', Struct.INT32),
 ('size', Struct.INT32),
 ('...', 8),
])
dslrFirmwareHeaderMagic = b'cnrjC012'

DslrFileHeader = Struct('DslrFileHeader', [
 ('name', Struct.STR % 12),
 ('size', Struct.INT32),
 ('offset', Struct.INT32),
 ('...', 12),
])

def _decrypt(data, little):
 return cryptXor55(0x87654321, data, little)

def _decryptBigEndian(data):
 return _decrypt(data, False)

def _decryptLittleEndian(data):
 return _decrypt(data, True)

def _findDecryptFunc(file):
 file.seek(0)
 data = file.read(DslrFirmwareHeader.size)
 for f in [_decryptBigEndian, _decryptLittleEndian]:
  header = DslrFirmwareHeader.unpack(f(data))
  if header and header.magic == dslrFirmwareHeaderMagic:
   return f

def isDslrFirmware(file):
 return _findDecryptFunc(file) is not None

def decryptDslrFirmware(file):
 decrypt = _findDecryptFunc(file)
 if decrypt is None:
  raise Exception('Cannot decrypt')

 file.seek(0)
 return io.BytesIO(decrypt(file.read()))

def readDslrFirmware(file):
 header = DslrFirmwareHeader.unpack(file)

 if header.magic != dslrFirmwareHeaderMagic:
  raise Exception('Wrong magic')

 file.seek(DslrFirmwareHeader.size + header.nFiles * DslrFileHeader.size)
 if (sum(file.read()) & 0xffffffff) != header.checksum:
  raise Exception('Wrong checksum')

 if header.version.isdigit():
  version = header.version.decode('ascii')
 else:
  version = parse16le(header.version)
  version = '%x.%02x' % (version & 0xff, version >> 8)

 files = []
 off = DslrFirmwareHeader.size
 for i in range(header.nFiles):
  f = DslrFileHeader.unpack(file, off)
  files.append((f.name.rstrip(b'\0').decode('ascii'), FilePart(file, f.offset, f.size)))
  off += DslrFileHeader.size

 return DslrFirmwareFile(int(header.model), version, files)
