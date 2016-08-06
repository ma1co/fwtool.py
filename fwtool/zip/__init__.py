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
zipHeaderMagic = 'PK\x03\x04'


class MyZipExtFile:
 def __init__(self, zipFile):
  self.zipFile = zipFile
  self.pos = self.zipFile._fileobj.tell()

 def read(self, n=-1):
  self.zipFile._fileobj.seek(self.pos)
  contents = self.zipFile.read(n)
  self.pos = self.zipFile._fileobj.tell()
  return contents


def isZip(file):
 """Returns true if the file provided is a zip file"""
 header = ZipHeader.unpack(file)
 return header and header.magic == zipHeaderMagic

def readZip(file):
 """Takes the a .zip file and returns the contained files"""
 zip = zipfile.ZipFile(file, 'r')
 for member in zip.infolist():
  yield ZipFile(
   path = member.filename,
   size = member.file_size,
   mtime = time.mktime(member.date_time + (-1, -1, -1)),
   contents = MyZipExtFile(zip.open(member)),
  )
