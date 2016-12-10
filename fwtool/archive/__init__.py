from collections import namedtuple

UnixFile = namedtuple('UnixFile', 'path, size, mtime, mode, uid, gid, contents')

from . import axfs, cpio, cramfs, ext2, fat, gz, lzpt, tar

def _findType(data):
 types = [
  (axfs.isAxfs, axfs.readAxfs),
  (cpio.isCpio, cpio.readCpio),
  (cramfs.isCramfs, cramfs.readCramfs),
  (ext2.isExt2, ext2.readExt2),
  (fat.isFat, fat.readFat),
  (gz.isGzip, gz.readGzip),
  (lzpt.isLzpt, lzpt.readLzpt),
  (tar.isTar, tar.readTar),
 ]

 for detect, read in types:
  if detect(data):
   return read
 return None

def isArchive(data):
 return _findType(data) is not None

def readArchive(data):
 return _findType(data)(data)
