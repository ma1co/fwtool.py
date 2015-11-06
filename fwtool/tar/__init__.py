"""A simple parser for tar archives"""

import io
from tarfile import TarFile

def readTar(data):
 """Takes the contents of a .tar file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with TarFile(fileobj=io.BytesIO(data)) as f:
  for member in f:
   if member.isfile():
    files[member.name] = memoryview(data)[member.offset_data:member.offset_data+member.size]
 return files
