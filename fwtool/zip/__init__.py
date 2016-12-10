"""A simple parser for zip archives"""

from collections import namedtuple
import time
import zipfile

ZipFile = namedtuple('ZipFile', 'path, size, mtime, contents')

from ..util import *

ZipHeader = Struct('ZipHeader', [
 ('magic', Struct.STR % 4),
 ('...', 26),
])
zipHeaderMagic = b'PK\x03\x04'


class _MySharedFile(object):
 def __init__(self, file):
  self._file = file
  self._pos = file.tell()

 def read(self, n=-1):
  self._file.seek(self._pos)
  data = self._file.read(n)
  self._pos = self._file.tell()
  return data

 def close(self):
  if self._file is not None:
   self._file.close()
   self._file = None


def isZip(file):
 """Returns true if the file provided is a zip file"""
 header = ZipHeader.unpack(file)
 return header and header.magic == zipHeaderMagic

def readZip(file):
 """Takes the a .zip file and returns the contained files"""
 zip = zipfile.ZipFile(file, 'r')
 for member in zip.infolist():
  contents = zip.open(member)
  if contents._fileobj.__class__.__name__ != '_SharedFile':
   # Python 2
   contents._fileobj = _MySharedFile(contents._fileobj)
  yield ZipFile(
   path = member.filename,
   size = member.file_size,
   mtime = time.mktime(member.date_time + (-1, -1, -1)),
   contents = contents,
  )
