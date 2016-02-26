"""A simple parser for zip archives"""

from collections import namedtuple
import shutil
import time
import zipfile

ZipFile = namedtuple('ZipFile', 'size, mtime, extractTo')

from ..util import *

ZipHeader = Struct('ZipHeader', [
 ('magic', Struct.STR % 4),
 ('...', 26),
])
zipHeaderMagic = 'PK\x03\x04'

def isZip(file):
 """Returns true if the file provided is a zip file"""
 header = ZipHeader.unpack(file)
 return header and header.magic == zipHeaderMagic

def readZip(file):
 """Takes the a .zip file and returns a dict of the contained files"""
 files = {}
 zip = zipfile.ZipFile(file, 'r')
 for member in zip.infolist():
  files[member.filename] = ZipFile(
   size = member.file_size,
   mtime = time.mktime(member.date_time + (-1, -1, -1)),
   extractTo = lambda dstFile, member=member: shutil.copyfileobj(zip.open(member), dstFile),
  )
 return files
