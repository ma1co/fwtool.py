"""A parser for axfs file system images"""

from stat import *
import zlib

from . import *
from ..io import *
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
axfsHeaderMagic = b'\x48\xA0\xE4\xCD'
axfsHeaderSignature = b'Advanced XIP FS\0'

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

def isAxfs(file):
 header = AxfsHeader.unpack(file)
 return header and header.magic == axfsHeaderMagic and header.signature == axfsHeaderSignature

def readAxfs(file):
 header = AxfsHeader.unpack(file)
 if header.magic != axfsHeaderMagic or header.signature != axfsHeaderSignature:
  raise Exception('Wrong magic')

 regions = {}
 tables = {}
 for i, k in enumerate(axfsRegions):
  region = AxfsRegionDesc.unpack(file, parse64be(header.regions[i*8:(i+1)*8]))
  regions[k] = FilePart(file, region.offset, region.size)
  if i >= 4:
   regionData = regions[k].read()
   tables[k] = [sum([ord(regionData[j*region.maxIndex+i:j*region.maxIndex+i+1]) << (8*j) for j in range(region.tableByteDepth)]) for i in range(region.maxIndex)]

 def readInode(id, path=''):
  size = tables['fileSize'][id]
  nameOffset = tables['nameOffset'][id]
  mode = tables['modes'][tables['modeIndex'][id]]
  uid = tables['uids'][tables['modeIndex'][id]]
  gid = tables['gids'][tables['modeIndex'][id]]
  numEntries = tables['numEntries'][id]
  arrayIndex = tables['arrayIndex'][id]

  name = b''
  regions['strings'].seek(nameOffset)
  while b'\0' not in name:
   name += regions['strings'].read(1024)
  name = name.partition(b'\0')[0].decode('ascii')

  path += name if id != 0 else ''
  isDir = S_ISDIR(mode)

  def generateChunks(arrayIndex=arrayIndex, numEntries=numEntries, size=size):
   read = 0
   for i in range(numEntries):
    nodeType = tables['nodeType'][arrayIndex + i]
    nodeIndex = tables['nodeIndex'][arrayIndex + i]
    if nodeType == 0:
     regions['xip'].seek(nodeIndex << 12)
     contents = regions['xip'].read(4096)
    elif nodeType == 1:
     cnodeIndex = tables['cnodeIndex'][nodeIndex]
     regions['compressed'].seek(tables['cblockOffset'][cnodeIndex])
     contents = zlib.decompress(regions['compressed'].read(tables['cblockOffset'][cnodeIndex+1] - tables['cblockOffset'][cnodeIndex]))
    elif nodeType == 2:
     regions['byteAligned'].seek(tables['banodeOffset'][nodeIndex])
     contents = regions['byteAligned'].read(size - read)
    else:
     raise Exception('Unknown type')
    yield contents
    read += len(contents)

  yield UnixFile(
   path = path,
   size = size if not isDir else 0,
   mtime = 0,
   mode = mode,
   uid = uid,
   gid = gid,
   contents = ChunkedFile(generateChunks, size) if S_ISREG(mode) or S_ISLNK(mode) else None,
  )

  if isDir:
   for i in range(numEntries):
    for f in readInode(arrayIndex + i, path + '/'):
     yield f

 for f in readInode(0):
  yield f
