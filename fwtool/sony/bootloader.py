"""Parser for bootloader partitions"""

from collections import namedtuple

from ..io import *
from ..util import *

BootFile = namedtuple('BootFile', 'name, size, version, loadaddr, contents')

BootHeader = Struct('BootHeader', [
 ('magic', Struct.STR % 4),
 ('...', 4),
 ('pageSize', Struct.INT32),
 ('...', 4),
 ('pageSizeAlt', Struct.INT32),
 ('...', 44),
])
bootHeaderMagic1 = b'EXBL'
bootHeaderMagic2 = b'INFO'

BootFileHeader1 = Struct('BootFileHeader1', [
 ('page', Struct.INT32),
 ('nPage', Struct.INT32),
 ('checksum', Struct.INT32),
 ('version', Struct.INT32),
 ('loadaddr', Struct.INT32),
 ('...', 4),
 ('name', Struct.STR % 40),
])

BootFileHeader2 = Struct('BootFileHeader2', [
 ('die', Struct.INT32),
 ('plane', Struct.INT32),
 ('block', Struct.INT32),
 ('page', Struct.INT32),
 ('nPage', Struct.INT32),
 ('...', 4),
 ('checksum', Struct.INT32),
 ('version', Struct.INT32),
 ('loadaddr', Struct.INT32),
 ('...', 4),
 ('name', Struct.STR % 24),
])

def isBootloader(file):
 header = BootHeader.unpack(file)
 return header and (header.magic == bootHeaderMagic1 or header.magic == bootHeaderMagic2)

def readBootloader(file):
 header = BootHeader.unpack(file)

 if header.magic == bootHeaderMagic1:
  FileHeader = BootFileHeader1
 elif header.magic == bootHeaderMagic2:
  FileHeader = BootFileHeader2
 else:
  raise Exception('Unknown magic')

 pageSize = header.pageSize
 if pageSize == 0xffffffff:
  pageSize = header.pageSizeAlt

 for off in range(BootHeader.size, pageSize, FileHeader.size):
  h = FileHeader.unpack(file, off)
  name = h.name.rstrip(b'\0\xff').decode('ascii')
  if name != '':
   version = '%d.%02d.%02d' % ((h.version >> 24) & 0xff, (h.version >> 16) & 0xff, (h.version >> 8) & 0xff) if h.version != 0 else None
   o = h.page * pageSize
   s = h.nPage * pageSize
   yield BootFile(name, s, version, h.loadaddr, FilePart(file, o, s))
