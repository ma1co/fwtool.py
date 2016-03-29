"""Parser for the SDM partition table at the beginning of /dev/nflasha"""
# Kernel source: fs/partitions/sdm_partition_table.h

from ..io import *
from ..util import *

SdmPartitionTableHeader = Struct('SdmPartitionTableHeader', [
 ('magic', Struct.STR % 4),
 ('version', Struct.STR % 4),
 ('nPartition', Struct.INT32),
 ('...', 20),
])
sdmPartitionTableHeaderMagic = '8246'
sdmPartitionTableHeaderVersion = '1.00'

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

 for i in xrange(header.nPartition):
  partition = SdmPartition.unpack(file, SdmPartitionTableHeader.size + i*SdmPartition.size)
  if partition.type != 0:
   yield i+1, FilePart(file, partition.start, partition.size)
