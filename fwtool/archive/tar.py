"""A simple parser for tar archives"""

import io
from stat import *
import tarfile

from . import *
from ..util import *

TarHeader = Struct('TarHeader', [
 ('...', 257),
 ('magic', Struct.STR % 6),
 ('version', Struct.STR % 2),
 ('...', 235),
])
tarHeaderMagic = 'ustar\x00'

def _convertFileType(type):
 return {
  tarfile.REGTYPE: S_IFREG,
  tarfile.LNKTYPE: S_IFLNK,
  tarfile.SYMTYPE: S_IFLNK,
  tarfile.CHRTYPE: S_IFCHR,
  tarfile.BLKTYPE: S_IFBLK,
  tarfile.DIRTYPE: S_IFDIR,
  tarfile.FIFOTYPE: S_IFIFO,
 }.get(type, S_IFREG)

def isTar(data):
 """Returns true if the data provided is a tar file"""
 return len(data) >= TarHeader.size and TarHeader.unpack(data).magic == tarHeaderMagic

def readTar(data):
 """Takes the contents of a .tar file and returns a dict containing the name and contents of the contained files"""
 files = {}
 with tarfile.TarFile(fileobj=io.BytesIO(data)) as f:
  for member in f:
   files['/' + member.name] = UnixFile(
    size = member.size,
    mtime = member.mtime,
    mode = _convertFileType(member.type) | member.mode,
    uid = member.uid,
    gid = member.gid,
    contents = f.extractfile(member).read() if member.isfile() else None,
   )
 return files
