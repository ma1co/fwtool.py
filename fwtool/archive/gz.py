"""A simple parser for gzip archives"""

import gzip
import shutil
from stat import *

from . import *
from ..util import *

GzipHeader = Struct('GzipHeader', [
 ('magic', Struct.STR % 2),
 ('...', 8),
])
gzipHeaderMagic = '\x1f\x8b'

def isGzip(file):
 """Returns true if the file provided is a gzip file"""
 header = GzipHeader.unpack(file)
 return header and header.magic == gzipHeaderMagic

def readGzip(file):
 """Unpacks a .gz file and returns the contained file"""
 file.seek(0)
 gz = gzip.GzipFile(fileobj=file, mode='r')
 yield UnixFile(
  path = '',
  size = -1,
  mtime = 0,
  mode = S_IFREG,
  uid = 0,
  gid = 0,
  extractTo = lambda dstFile: shutil.copyfileobj(gz, dstFile),
 )
