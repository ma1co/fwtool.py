"""Parser for the SDM partition table at the beginning of /dev/nflasha"""
# Kernel source: fs/partitions/sdm_partition_table.h

import shutil

from ..io import *
from ..util import *

SdmPartitionTableHeader = Struct('SdmPartitionTableHeader', [
 ('magic', Struct.STR % 4),
 ('version', Struct.STR % 4),
 ('nPartition', Struct.INT32),
 ('...', 20),
])
sdmPartitionTableHeaderMagic = b'8246'
sdmPartitionTableHeaderVersion = b'1.00'

SdmPartition = Struct('SdmPartition', [
 ('start', Struct.INT32),
 ('size', Struct.INT32),
 ('type', Struct.INT32),
 ('flag', Struct.INT32),
])

def isPartitionTable(file):
 header = SdmPartitionTableHeader.unpack(file)
 return header and header.magic == sdmPartitionTableHeaderMagic

def readPartitionTable(file):
 header = SdmPartitionTableHeader.unpack(file)

 if header.magic != sdmPartitionTableHeaderMagic:
  raise Exception('Wrong magic')
 if header.version != sdmPartitionTableHeaderVersion:
  raise Exception('Wrong version')

 for i in range(header.nPartition):
  partition = SdmPartition.unpack(file, SdmPartitionTableHeader.size + i*SdmPartition.size)
  if partition.flag & 1:
   yield i+1, FilePart(file, partition.start, partition.size)

def writePartitions(partitions, outFile):
 sectorSize = 0x200

 outFile.write(SdmPartitionTableHeader.pack(
  magic = sdmPartitionTableHeaderMagic,
  version = sdmPartitionTableHeaderVersion,
  nPartition = len(partitions),
 ))
 outFile.write(b'\xff' * (sectorSize - SdmPartitionTableHeader.size))

 parts = []
 for f in partitions:
  o = outFile.tell()
  f.seek(0)
  shutil.copyfileobj(f, outFile)
  if outFile.tell() % sectorSize:
   outFile.write(b'\xff' * (sectorSize - outFile.tell() % sectorSize))
  parts.append((o, outFile.tell() - o))

 outFile.seek(SdmPartitionTableHeader.size)
 for o, s in parts:
  outFile.write(SdmPartition.pack(
   start = o,
   size = s,
   type = 1,
   flag = 0xffffffff,
  ))
