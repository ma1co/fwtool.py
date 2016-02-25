"""A parser for axfs file system images"""

from stat import *
import zlib

from . import *
from ..util import *

AxfsHeader = Struct('AxfsHeader', [
 ('magic', Struct.STR % 4),
 ('signature', Struct.STR % 16),
 ('digest', Struct.STR % 40),
 ('blockSize', Struct.INT32),
 ('files', Struct.INT64),
 ('size', Struct.INT64),
 ('blocks', Struct.INT64),
 ('mmapSize', Struct.INT64),
 ('regions', Struct.STR % 144),
 ('...', 13),
], Struct.BIG_ENDIAN)
axfsHeaderMagic = '\x48\xA0\xE4\xCD'
axfsHeaderSignature = 'Advanced XIP FS\x00'

AxfsRegionDesc = Struct('AxfsRegionDesc', [
 ('offset', Struct.INT64),
 ('size', Struct.INT64),
 ('compressedSize', Struct.INT64),
 ('maxIndex', Struct.INT64),
 ('tableByteDepth', Struct.INT8),
 ('incore', Struct.INT8),
], Struct.BIG_ENDIAN)

axfsRegions = [
 'strings',
 'xip',
 'byteAligned',
 'compressed',

 # tableRegions:
 'nodeType',
 'nodeIndex',
 'cnodeOffset',
 'cnodeIndex',
 'banodeOffset',
 'cblockOffset',
 'fileSize',
 'nameOffset',
 'numEntries',
 'modeIndex',
 'arrayIndex',
 'modes',
 'uids',
 'gids',
]

def isAxfs(data):
 if len(data) >= AxfsHeader.size:
  header = AxfsHeader.unpack(data)
  return header.magic == axfsHeaderMagic and header.signature == axfsHeaderSignature
 return False

def readAxfs(data):
 header = AxfsHeader.unpack(data)
 if header.magic != axfsHeaderMagic or header.signature != axfsHeaderSignature:
  raise Exception('Wrong magic')

 regions = {}
 tables = {}
 for i, k in enumerate(axfsRegions):
  region = AxfsRegionDesc.unpack(data, parse64be(header.regions[i*8:(i+1)*8]))
  regionData = data[region.offset:region.offset+region.size]
  if i >= 4:
   tables[k] = [sum([ord(regionData[j * region.maxIndex + i]) << (8*j) for j in xrange(region.tableByteDepth)]) for i in xrange(region.maxIndex)]
  else:
   regions[k] = regionData

 files = {}
 def readInode(id, path=''):
  size = tables['fileSize'][id]
  nameOffset = tables['nameOffset'][id]
  name = regions['strings'][nameOffset:regions['strings'].index('\x00', nameOffset)]
  mode = tables['modes'][tables['modeIndex'][id]]
  uid = tables['uids'][tables['modeIndex'][id]]
  gid = tables['gids'][tables['modeIndex'][id]]
  numEntries = tables['numEntries'][id]
  arrayIndex = tables['arrayIndex'][id]

  path += name if id != 0 else ''
  isDir = S_ISDIR(mode)

  if not isDir:
   contents = ''
   for i in xrange(numEntries):
    nodeType = tables['nodeType'][arrayIndex + i]
    nodeIndex = tables['nodeIndex'][arrayIndex + i]
    if nodeType == 0:
     o = nodeIndex << 12
     contents += regions['xip'][o:o+4096]
    elif nodeType == 1:
     o = tables['cblockOffset'][tables['cnodeIndex'][nodeIndex]]
     contents += zlib.decompress(regions['compressed'][o:])
    elif nodeType == 2:
     o = tables['banodeOffset'][nodeIndex]
     contents += regions['byteAligned'][o:o+size]
  else:
   contents = None

  files[path] = UnixFile(
   size = size if not isDir else 0,
   mtime = 0,
   mode = mode,
   uid = uid,
   gid = gid,
   contents = contents,
  )

  if isDir:
   for i in xrange(numEntries):
    readInode(arrayIndex + i, path + '/')

 readInode(0)
 return files
