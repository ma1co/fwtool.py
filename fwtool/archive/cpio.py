"""A simple parser for "new ascii format" cpio archives"""

from . import *
from ..io import *
from ..util import *

CpioHeader = Struct('CpioHeader', [
 ('magic', Struct.STR % 6),
 ('inode', Struct.STR % 8),
 ('mode', Struct.STR % 8),
 ('uid', Struct.STR % 8),
 ('gid', Struct.STR % 8),
 ('nlink', Struct.STR % 8),
 ('mtime', Struct.STR % 8),
 ('size', Struct.STR % 8),
 ('...', 32),
 ('nameSize', Struct.STR % 8),
 ('check', Struct.STR % 8),
])
cpioHeaderMagic = b'070701'

def isCpio(file):
 """Returns true if the file provided is a cpio file"""
 header = CpioHeader.unpack(file)
 return header and header.magic == cpioHeaderMagic

def _roundUp(n, i):
 return (n + i - 1) // i * i

def readCpio(file):
 """Unpacks a cpio archive and returns the contained files"""
 offset = 0
 while True:
  header = CpioHeader.unpack(file, offset)
  if header.magic != cpioHeaderMagic:
   raise Exception('Wrong magic')
  header = CpioHeader.tuple._make(int(i, 16) for i in header)

  file.seek(offset + CpioHeader.size)
  name = file.read(header.nameSize).rstrip(b'\0').decode('ascii')

  if name == 'TRAILER!!!':
   break

  dataStart = _roundUp(offset + CpioHeader.size + header.nameSize, 4)
  offset = _roundUp(dataStart + header.size, 4)

  yield UnixFile(
   path = '/' + name,
   size = header.size,
   mtime = header.mtime,
   mode = header.mode,
   uid = header.uid,
   gid = header.gid,
   contents = FilePart(file, dataStart, header.size),
  )
