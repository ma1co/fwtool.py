from ..io import *
from ..util import *

def readPartitionTable(file):
 file.read(8)
 numPartitions = parse32le(file.read(4))
 file.read(20)
 for i in xrange(1, numPartitions + 1):
  offset = parse32le(file.read(4))
  length = parse32le(file.read(4))
  type = parse32le(file.read(4))
  file.read(4)
  if type:
   yield i, FilePart(file, offset, length)
