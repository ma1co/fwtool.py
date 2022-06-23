"""Decrypter & parser for very old firmware files which had to be copied to a memory stick"""

from collections import namedtuple, OrderedDict
from stat import *
import io
import os
import re

try:
 from Cryptodome.Hash import SHA
 from Cryptodome.Util.strxor import strxor
except ImportError:
 from Crypto.Hash import SHA
 from Crypto.Util.strxor import strxor

from . import constants
from .. import archive
from ..io import *


MsFirmFile = namedtuple('MsFirmFile', 'model, region, version, fs, files')


class MsCrypter(object):
 def __init__(self, name, key):
  self.name = name
  self.key = key

 def _calcHash(self, data):
  hash = SHA.new(strxor(self.key, b'\x36' * 0x40) + data).digest()
  return SHA.new(strxor(self.key, b'\x5c' * 0x40) + hash).digest()

 def checkHeaderHash(self, header):
  return self._calcHash(header[:-20] + b'\0' * 20) == header[-20:]

 def _cipher(self, data):
  xorKey = io.BytesIO()
  digest = self.key[:20]
  while xorKey.tell() < len(data):
   digest = SHA.new(digest + self.key[20:40]).digest()
   xorKey.write(digest)
  return strxor(data, xorKey.getvalue()[:len(data)])

 def _decrypt(self, file, off, size):
  file.seek(off)
  header = file.read(0x80)
  data = file.read(size)

  if not self.checkHeaderHash(header):
   raise Exception('Wrong header hash')
  if self._calcHash(data) != header[:20]:
   raise Exception('Wrong data hash')

  return self._cipher(data)

 def decrypt(self, file, off, size):
  return ChunkedFile(lambda: (yield self._decrypt(file, off, size)))

 def encrypt(self, data, outFile):
  data = self._cipher(data)
  header = self._calcHash(data).ljust(0x80, b'\0')
  header = header[:-20] + self._calcHash(header)
  outFile.write(header + data)


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


def _dumpContents(files, size):
 data = '\n'.join([
  '[total number of files]',
  'total_num=%x' % len(files),
  '\n',
 ])
 offset = size
 for i, file in enumerate(files):
  file.contents.seek(0, os.SEEK_END)
  sz = file.contents.tell()
  file.contents.seek(0)
  data += '\n'.join([
   '[header]' if i == 0 else '[program data]',
   'fnum=%x' % i,
   'name=%s' % file.path.lstrip('/'),
   'offset=%x' % offset,
   'size=%x' % sz,
   'cksum=%x' % 0,
   'progress=%x' % 0,
   'encrypt=yes',
   '\n',
  ])
  offset += sz
 data = data.ljust(size - 0x40, ' ').encode('ascii')

 header = '\n'.join([
  'FV %02x' % 0,
  'SV %02x' % 0,
  '',
  '[alsiz]',
  'datasize=%08x' % (size - 0x40),
  '',
  '[hdsm]',
  'chksum=%08x' % sum(data),
  '\n',
 ]).encode('ascii')
 if len(header) != 0x40:
  raise Exception('Wrong header size')

 return header + data


def _dumpHeader(model, region, version):
 return '\n'.join([
  '[version]',
  'ver=%04x' % version,
  '[model]',
  'model=%08x' % model,
  '[region]',
  'region=%08x' % region,
  '',
 ]).encode('ascii')


def _toUnixFile(path, file):
 return archive.UnixFile(
  path = path,
  size = -1,
  mtime = 0,
  mode = S_IFREG | 0o775,
  uid = 0,
  gid = 0,
  contents = file,
 )


_keys = OrderedDict([
 ('CXD4105_ms', constants.key_cxd4105_ms),
 ('CXD4108_ms', constants.key_cxd4108_ms),
])

def _findDecrypter(file):
 file.seek(0)
 header = file.read(0x80)
 for name, key in _keys.items():
  crypter = MsCrypter(name, key)
  if crypter.checkHeaderHash(header):
   return crypter


def isMsFirm(file):
 file.seek(0)
 header = file.read(0x80)
 return len(header) == 0x80 and header[20:-20] == b'\0' * 88 and _findDecrypter(file)


def readMsFirm(file):
 crypter = _findDecrypter(file)
 if crypter is None:
  raise Exception('Cannot decrypt')

 contentFile = _toUnixFile('/cntent.dat', crypter.decrypt(file, 0, 0x5000))
 data = contentFile.contents.read()
 contentFile.contents.seek(0)

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
  files.append(_toUnixFile('/' + name, crypter.decrypt(file, offset + (i + 1) * 0x80, size)))

 header = _parseContents(files[0].contents.read().decode('ascii'))
 files[0].contents.seek(0)
 version = int(header[0]['ver'], 16)
 return crypter.name, MsFirmFile(
  version = '%x.%02x' % (version >> 8, version & 0xff),
  model = int(header[1]['model'], 16),
  region = int(header[2]['region'], 16),
  fs = files[2],
  files = [contentFile] + files,
 )


def writeMsFirm(keyName, msfirm, outFile):
 crypter = MsCrypter(keyName, _keys[keyName])

 version = re.match('^(\d)\.(\d{2})$', msfirm.version)
 if not version:
  raise Exception('Cannot parse version string')
 version = (int(version.group(1), 16) << 8) + int(version.group(2), 16)

 files = [
  _toUnixFile('/defhd.dat', io.BytesIO(_dumpHeader(msfirm.model, msfirm.region, version))),
  _toUnixFile('/partinf.tbl', io.BytesIO()),
  _toUnixFile('/BodyUdtr.img', msfirm.fs),
 ]
 files += msfirm.files if msfirm.files else [_toUnixFile('/av_udtr.bin', io.BytesIO())]

 crypter.encrypt(_dumpContents(files, 0x5000), outFile)
 for file in files:
  crypter.encrypt(file.contents.read(), outFile)
 outFile.write(b'\0' * (0x8000 - outFile.tell()))
