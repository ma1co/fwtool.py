from collections import namedtuple

UnixFile = namedtuple('UnixFile', 'size, mtime, mode, uid, gid, contents')

from . import axfs, cramfs, ext2, fat, lzpt, tar

def _findType(data):
 types = [
  (axfs.isAxfs, axfs.readAxfs),
  (cramfs.isCramfs, cramfs.readCramfs),
  (ext2.isExt2, ext2.readExt2),
  (fat.isFat, fat.readFat),
  (lzpt.isLzpt, lzpt.readLzpt),
  (tar.isTar, tar.readTar),
 ]

 for detect, read in types:
  if detect(data):
   return read
 return None

def isArchive(data):
 return _findType(data) != None

def readArchive(data):
 return _findType(data)(data)
