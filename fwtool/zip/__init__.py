"""A simple parser for zip archives"""

import io
from zipfile import ZipFile

from ..util import *

ZipHeader = Struct('ZipHeader', [
 ('magic', Struct.STR % 4),
 ('...', 26),
])
zipHeaderMagic = 'PK\x03\x04'

ZipEocdHeader = Struct('ZipEocdHeader', [
 ('magic', Struct.STR % 4),
 ('...', 16),
 ('commentSize', Struct.INT16),
])
zipEocdHeaderMagic = 'PK\x05\x06'

def findZip(data):
 """Guesses the location of a zip archive when there is additional data around it, returns its contents"""
 headerOffset = data.find(zipHeaderMagic)
 header = ZipHeader.unpack(data, headerOffset)

 eocdOffset = data.rfind(zipEocdHeaderMagic)
 eocdHeader = ZipEocdHeader.unpack(data, eocdOffset)

 return memoryview(data)[headerOffset:eocdOffset+ZipEocdHeader.size+eocdHeader.commentSize]

def isZip(data):
 """Returns true if the data provided is a zip file"""
 return len(data) >= ZipHeader.size and ZipHeader.unpack(data).magic == zipHeaderMagic

def readZip(data):
 """Takes the contents of a .zip file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with ZipFile(io.BytesIO(data), 'r') as f:
  for name in f.namelist():
   files[name] = f.read(name)
 return files
