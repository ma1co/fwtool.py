"""Parser for the package format used by repackaged updater executables

Since 2022, Sony has been re-releasing updaters (also for older cameras) in a new
self-extracting executable. The files are appended to the exe in this format (all
values little endian):

  PackageHeader
  for each group (numGroups):
   GroupHeader, followed by the group name (UTF-16LE, nameLength characters)
   for each file in the group (numFiles):
    FileHeader, followed by the file name (UTF-16LE, nameLength characters)
    and the modification time (FILETIME, 64 bit)
  file contents, concatenated in the order of the directory above

A group name is either a special location ('!!!' followed by a GUID) or a relative
folder like 'Resource\\'.
"""

from ..io import *
from ..util import *

PackageFile = namedtuple('PackageFile', 'path, size, mtime, contents')

PackageHeader = Struct('PackageHeader', [
 ('creationTime', Struct.INT64),
 ('expirationTime', Struct.INT64),
 ('unknown1', Struct.INT32),
 ('unknown2', Struct.INT32),
 ('numGroups', Struct.INT32),
])

GroupHeader = Struct('GroupHeader', [
 ('nameLength', Struct.INT32),
 ('numFiles', Struct.INT32),
])

FileHeader = Struct('FileHeader', [
 ('nameLength', Struct.INT32),
 ('size', Struct.INT32),
])

specialGroupPrefix = u'!!!'
maxGroups = 0x100
maxFiles = 0x1000
maxNameLength = 0x400

def _fileTimeToUnix(fileTime):
 return (fileTime - 116444736000000000) / 10000000.

def _readName(file, offset, length):
 file.seek(offset)
 data = file.read(2 * length)
 if len(data) != 2 * length:
  raise ValueError('Name truncated')
 name = data.decode('utf-16le')
 if any(c < u' ' for c in name):
  raise ValueError('Invalid name')
 return name

def _readDirectory(file):
 header = PackageHeader.unpack(file)
 if not header or not 0 < header.numGroups <= maxGroups:
  raise ValueError('Invalid header')
 offset = PackageHeader.size

 files = []
 for i in range(header.numGroups):
  group = GroupHeader.unpack(file, offset)
  if not group or not 0 < group.nameLength <= maxNameLength or group.numFiles > maxFiles:
   raise ValueError('Invalid group header')
  groupName = _readName(file, offset + GroupHeader.size, group.nameLength)
  offset += GroupHeader.size + 2 * group.nameLength
  prefix = u'' if groupName.startswith(specialGroupPrefix) else groupName.replace(u'\\', u'/').rstrip(u'/') + u'/'

  for j in range(group.numFiles):
   fileHeader = FileHeader.unpack(file, offset)
   if not fileHeader or not 0 < fileHeader.nameLength <= maxNameLength:
    raise ValueError('Invalid file header')
   name = _readName(file, offset + FileHeader.size, fileHeader.nameLength)
   offset += FileHeader.size + 2 * fileHeader.nameLength
   file.seek(offset)
   mtime = parse64le(file.read(8))
   offset += 8
   files.append((prefix + name.replace(u'\\', u'/'), fileHeader.size, _fileTimeToUnix(mtime)))

 return offset, files

def isPackage(file):
 try:
  offset, files = _readDirectory(file)
 except ValueError:
  return False
 file.seek(0, 2)
 return offset + sum(size for path, size, mtime in files) <= file.tell()

def readPackage(file):
 offset, files = _readDirectory(file)
 for path, size, mtime in files:
  yield PackageFile(
   path = path,
   size = size,
   mtime = mtime,
   contents = FilePart(file, offset, size),
  )
  offset += size
