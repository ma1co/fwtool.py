"""A decoder for LZPT compressed image files"""
# Kernel source: arch/arm/include/asm/mach/warmboot.h
# Kernel source: arch/arm/mach-cxd90014/include/mach/cmpr.h

import io
from stat import *

from . import *
from .. import lz77
from ..io import *
from ..util import *

# struct wbi_lzp_hdr
LzptHeader = Struct('LzptHeader', [
 ('magic', Struct.STR % 4),
 ('blockSize', Struct.INT32),
 ('tocOffset', Struct.INT32),
 ('tocSize', Struct.INT32),
])
# CMPR_LZPART_MAGIC
lzptHeaderMagic = b'TPZL'

# struct wbi_lzp_entry
LzptTocEntry = Struct('LzptTocEntry', [
 ('offset', Struct.INT32),
 ('size', Struct.INT32),
])

def isLzpt(file):
 """Checks if the LZTP header is present"""
 header = LzptHeader.unpack(file)
 return header and header.magic == lzptHeaderMagic

def readLzpt(file):
 """Decodes an LZTP image and returns its contents"""
 header = LzptHeader.unpack(file)

 if header.magic != lzptHeaderMagic:
  raise Exception('Wrong magic')

 tocEntries = [LzptTocEntry.unpack(file, header.tocOffset + offset) for offset in range(0, header.tocSize, LzptTocEntry.size)]

 def generateChunks():
  for entry in tocEntries:
   file.seek(entry.offset)
   block = io.BytesIO(file.read(entry.size))

   read = 0
   while read < 2 ** header.blockSize:
    contents = lz77.inflateLz77(block)
    yield contents
    read += len(contents)

 yield UnixFile(
  path = '',
  size = -1,
  mtime = 0,
  mode = S_IFREG,
  uid = 0,
  gid = 0,
  contents = ChunkedFile(generateChunks),
 )


class LzptInvariantError(Exception):
 pass


def readToc(file):
 """Returns (header, tocEntries) without decoding any block"""
 header = LzptHeader.unpack(file)
 if header.magic != lzptHeaderMagic:
  raise Exception('Wrong magic')
 tocEntries = [LzptTocEntry.unpack(file, header.tocOffset + offset)
               for offset in range(0, header.tocSize, LzptTocEntry.size)]
 return header, tocEntries


def fileSize(file):
 file.seek(0, 2)
 size = file.tell()
 file.seek(0)
 return size


def checkLzpt(file, reference=None):
 """Checks the invariants the camera's NAND driver enforces on an LZPT image.

 The driver (kmod/nand.ko, mumin_lzp.c) masks the block offset with 0x1FF and
 prints "[LDEC WARN]Offset for lded_read should be 0, current = %d" when the
 result is not zero, then fails the read.  A misaligned container therefore
 makes /system unreadable: the camera never reaches the updater and cannot be
 recovered over USB.

 This matters because decoding does *not* catch it - readLzpt() accepts blocks
 at any offset, so a container can round-trip perfectly and still brick the
 camera.  Call this before flashing, or pass the stock image as `reference` to
 also require that the block table and the total size are unchanged (that keeps
 the on-flash layout identical, so a half-finished write stays decodable).

 Returns a dict describing the container; raises LzptInvariantError when an
 invariant is violated.
 """
 header, tocEntries = readToc(file)
 size = fileSize(file)

 unalignedOffsets = [i for i, entry in enumerate(tocEntries) if entry.offset % 512]
 unalignedSizes = [i for i, entry in enumerate(tocEntries) if entry.size % 512]

 if unalignedOffsets or unalignedSizes:
  raise LzptInvariantError(
   'Offset for lded_read should be 0, current = %d, please check img '
   '(%d of %d blocks have an offset and %d have a size that is not a multiple of 512; '
   'the camera cannot read this image - do not flash it)'
   % (tocEntries[unalignedOffsets[0]].offset % 512 if unalignedOffsets
      else tocEntries[unalignedSizes[0]].size % 512,
      len(unalignedOffsets), len(tocEntries), len(unalignedSizes)))

 if reference is not None:
  refHeader, refEntries = readToc(reference)
  refSize = fileSize(reference)
  if refEntries != tocEntries:
   differing = [i for i, (a, b) in enumerate(zip(refEntries, tocEntries)) if a != b]
   raise LzptInvariantError(
    'block table differs from the reference image (%d of %d entries; first difference '
    'at block %s) - the on-flash layout changed, so a write that is interrupted can no '
    'longer be recovered by simply re-flashing'
    % (len(differing), max(len(refEntries), len(tocEntries)),
       differing[0] if differing else '-'))
  if refSize != size:
   raise LzptInvariantError(
    'container size differs from the reference image (%d vs %d bytes)' % (size, refSize))

 return {
  'blockSize': 2 ** header.blockSize,
  'blocks': len(tocEntries),
  'size': size,
  'unalignedOffsets': unalignedOffsets,
  'unalignedSizes': unalignedSizes,
  'toc': tocEntries,
 }
