"""A simple parser for zip archives"""

import io
from zipfile import ZipFile

from ..util import *

def findZip(data):
 """Guesses the location of a zip archive when there is additional data around it, returns its contents"""
 start = data.find('PK\x03\x04')

 endOffset = len(data) - data[::-1].find('PK\x05\x06'[::-1]) - 4
 commentLen = parse16le(data[endOffset+20:endOffset+22])

 end = endOffset + 22 + commentLen
 return memoryview(data)[start:end]

def readZip(data):
 """Takes the contents of a .zip file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with ZipFile(io.BytesIO(data), 'r') as f:
  for name in f.namelist():
   files[name] = f.read(name)
 return files
