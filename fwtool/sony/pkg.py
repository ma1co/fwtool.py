"""Parser for the package container appended to newer updater executables"""

from collections import namedtuple

from ..io import FilePart
from ..util import *

PkgFile = namedtuple('PkgFile', 'path, size, mtime, contents')

PkgHeader = Struct('PkgHeader', [
 ('mtime', Struct.INT64),
 ('expiryTime', Struct.INT64),
 ('fileCount', Struct.INT32),
 ('...', 4),
 ('version', Struct.INT32),
])
pkgVersion = 1
pkgMaxFileCount = 0x100

PkgIdHeader = Struct('PkgIdHeader', [
 ('nameLength', Struct.INT32),
 ('fileCount', Struct.INT32),
])

PkgEntryHeader = Struct('PkgEntryHeader', [
 ('nameLength', Struct.INT32),
 ('size', Struct.INT32),
])

PkgEntryFooter = Struct('PkgEntryFooter', [
 ('mtime', Struct.INT64),
])

def convertFileTime(time):
 return time // 10000000 - 11644473600

def isPkg(file):
 """Returns true if the file provided is an updater package"""
 header = PkgHeader.unpack(file)
 return header is not None and header.version == pkgVersion and 0 < header.fileCount <= pkgMaxFileCount

def readPkg(file):
 """Takes an updater package and returns the contained files"""
 header = PkgHeader.unpack(file)
 if header.version != pkgVersion:
  raise Exception('Unknown package version')

 idHeader = PkgIdHeader.unpack(file, PkgHeader.size)
 offset = PkgHeader.size + PkgIdHeader.size + 2 * idHeader.nameLength

 entries = []
 for i in range(header.fileCount):
  entryHeader = PkgEntryHeader.unpack(file, offset)
  name = file.read(2 * entryHeader.nameLength).decode('utf-16-le')
  entryFooter = PkgEntryFooter.unpack(file, offset + PkgEntryHeader.size + 2 * entryHeader.nameLength)
  entries.append((name, entryHeader.size, entryFooter.mtime))
  offset += PkgEntryHeader.size + 2 * entryHeader.nameLength + PkgEntryFooter.size

 for name, size, mtime in entries:
  yield PkgFile(
   path = name,
   size = size,
   mtime = convertFileTime(mtime),
   contents = FilePart(file, offset, size),
  )
  offset += size
