"""A simple parser for tar archives"""

from StringIO import StringIO
from tarfile import TarFile

def readTar(data):
 """Takes the contents of a .tar file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with TarFile(fileobj=StringIO(data)) as f:
  for member in f:
   if member.isfile():
    files[member.name] = f.extractfile(member).read()
 return files
