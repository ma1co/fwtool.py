"""A simple parser for tar archives"""

import shutil
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

def isTar(file):
 """Returns true if the file provided is a tar file"""
 header = TarHeader.unpack(file)
 return header and header.magic == tarHeaderMagic

def readTar(file):
 """Unpacks a .tar file and returns a dict of the contained files"""
 file.seek(0)
 files = {}
 with tarfile.TarFile(fileobj=file) as tar:
  for member in tar:
   files['/' + member.name] = UnixFile(
    size = member.size,
    mtime = member.mtime,
    mode = _convertFileType(member.type) | member.mode,
    uid = member.uid,
    gid = member.gid,
    extractTo = lambda dstFile, srcFile=tar.extractfile(member): shutil.copyfileobj(srcFile, dstFile),
   )
 return files
