"""Decrypter & parser for very old firmware files which had to be copied to a memory stick"""

from collections import namedtuple
from stat import *
import io
import re

try:
 from Cryptodome.Hash import SHA
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Hash import SHA
 from Crypto.Util.strxor import strxor

from . import constants
from .. import archive


MsFirmFile = namedtuple('MsFirmFile', 'model, region, version, fs, files')


def _calcHash(data):
 hash = SHA.new(strxor(constants.msKey, b'\x36' * 0x40) + data).digest()
 return SHA.new(strxor(constants.msKey, b'\x5c' * 0x40) + hash).digest()


def _checkHeaderHash(header):
 return _calcHash(header[:-20] + b'\0' * 20) == header[-20:]


def _decrypt(file, off, size):
 file.seek(off)
 header = file.read(0x80)
 data = file.read(size)

 if not _checkHeaderHash(header):
  raise Exception('Wrong header hash')
 if _calcHash(data) != header[:20]:
  raise Exception('Wrong data hash')

 xorKey = io.BytesIO()
 digest = constants.msKey[:20]
 while xorKey.tell() < len(data):
  digest = SHA.new(digest + constants.msKey[20:40]).digest()
  xorKey.write(digest)
 return strxor(data, xorKey.getvalue()[:len(data)])


def _parseContents(data):
 sections = []
 section = None
 for l in data.split('\n'):
  hm = re.match('^\[(.+)\]$', l)
  pm = re.match('^(.+)=(.+)$', l)
  if hm:
   section = {}
   sections.append(section)
  elif pm and section is not None:
   section[pm.group(1)] = pm.group(2)
 return sections


def _toUnixFile(name, data):
 return archive.UnixFile(
  path = '/' + name,
  size = len(data),
  mtime = 0,
  mode = S_IFREG | 0o775,
  uid = 0,
  gid = 0,
  contents = io.BytesIO(data),
 )


def isMsFirm(file):
 file.seek(0)
 header = file.read(0x80)
 return len(header) == 0x80 and header[20:-20] == b'\0' * 88 and _checkHeaderHash(header)


def readMsFirm(file):
 data = _decrypt(file, 0, 0x5000)
 contentFile = _toUnixFile('cntent.dat', data)

 sections = _parseContents(data.decode('ascii'))
 checksum = int(sections[1]['chksum'], 16)
 total = int(sections[2]['total_num'], 16)

 if sum(data[0x40:]) != checksum:
  raise Exception('Invalid checksum')
 if len(sections) - 3 != total:
  raise Exception('Invalid number of files')

 files = []
 for i, f in enumerate(sections[3:]):
  name = f['name']
  offset = int(f['offset'], 16)
  size = int(f['size'], 16)
  data = _decrypt(file, offset + (i + 1) * 0x80, size)
  files.append(_toUnixFile(name, data))

 header = _parseContents(files[0].contents.read().decode('ascii'))
 files[0].contents.seek(0)
 version = int(header[0]['ver'], 16)
 return MsFirmFile(
  version = '%x.%02x' % (version >> 8, version & 0xff),
  model = int(header[1]['model'], 16),
  region = int(header[2]['region'], 16),
  fs = files[2],
  files = [contentFile] + files,
 )
