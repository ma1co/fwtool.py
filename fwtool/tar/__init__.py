"""A simple parser for tar archives"""

import io
from tarfile import TarFile

from ..util import *

TarHeader = Struct('TarHeader', [
 ('...', 257),
 ('magic', Struct.STR % 6),
 ('version', Struct.STR % 2),
 ('...', 235),
])
tarHeaderMagic = 'ustar\x00'

def isTar(data):
 """Returns true if the data provided is a tar file"""
 return len(data) >= TarHeader.size and TarHeader.unpack(data).magic == tarHeaderMagic

def readTar(data):
 """Takes the contents of a .tar file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with TarFile(fileobj=io.BytesIO(data)) as f:
  for member in f:
   if member.isfile():
    files[member.name] = memoryview(data)[member.offset_data:member.offset_data+member.size]
 return files
