"""Parser for mbr partition tables"""

import shutil

from ..io import *
from ..util import *

mbrSectorSize = 0x200

MbrHeader = Struct('MbrHeader', [
 ('...', 0x1be),
 ('partitions', Struct.STR % 0x40),
 ('magic', Struct.STR % 2),
])
mbrHeaderMagic = b'\x55\xaa'

MbrPartitionEntry = Struct('MbrPartitionEntry', [
 ('status', Struct.INT8),
 ('...', 3),
 ('type', Struct.INT8),
 ('...', 3),
 ('start', Struct.INT32),
 ('size', Struct.INT32),
])

def isMbr(file):
 header = MbrHeader.unpack(file)
 return header and header.magic == mbrHeaderMagic

def readMbr(file):
 header = MbrHeader.unpack(file)

 if header.magic != mbrHeaderMagic:
  raise Exception('Wrong magic')

 for i in range(4):
  partition = MbrPartitionEntry.unpack(header.partitions, i * MbrPartitionEntry.size)
  if partition.type:
   yield i+1, FilePart(file, partition.start * mbrSectorSize, partition.size * mbrSectorSize)

def writeMbr(partitions, outFile):
 outFile.write(b'\0' * MbrHeader.size)
 outFile.write(b'\xff' * (mbrSectorSize - MbrHeader.size))

 parts = []
 for f in partitions:
  o = outFile.tell()
  if f:
   f.seek(0)
   shutil.copyfileobj(f, outFile)
   if outFile.tell() % mbrSectorSize:
    outFile.write(b'\xff' * (mbrSectorSize - outFile.tell() % mbrSectorSize))
  parts.append((o, outFile.tell() - o, 1 if f else 0))

 outFile.seek(0)
 outFile.write(MbrHeader.pack(
  magic = mbrHeaderMagic,
  partitions = b''.join(MbrPartitionEntry.pack(status=0, type=type, start=start//mbrSectorSize, size=size//mbrSectorSize) for start, size, type in parts)
 ))
