"""A decoder for LZX compressed streams, as used in cabinet archives"""
# Based on the LZX decompressor of libmspack (mspack/lzxd.c) by Stuart Caie

from itertools import accumulate

lzxNumChars = 256
lzxNumPrimaryLengths = 7
lzxMinMatch = 2
lzxFrameSize = 32768
lzxMaxBits = 16
lzxLenTableSafety = 64

lzxPretreeSymbols = 20
lzxPretreeTableBits = 6
lzxMaintreeSymbols = lzxNumChars + 290 * 8
lzxMaintreeTableBits = 12
lzxLengthSymbols = 250
lzxLengthTableBits = 12
lzxAlignedSymbols = 8
lzxAlignedTableBits = 7

lzxBlockTypeVerbatim = 1
lzxBlockTypeAligned = 2
lzxBlockTypeUncompressed = 3

lzxPositionSlots = [30, 32, 34, 36, 38, 42, 50, 66, 98, 162, 290]
lzxExtraBits = [0 if slot < 4 else min(slot // 2 - 1, 17) for slot in range(290)]
lzxPositionBase = [0] + list(accumulate(1 << bits for bits in lzxExtraBits[:-1]))

def makeDecodeTable(symbols, tableBits, lengths):
 """Builds a lookup table decoding the canonical huffman code described by the given code lengths"""
 table = [0] * ((1 << tableBits) + symbols * 2)
 tableMask = 1 << tableBits
 bitMask = tableMask >> 1
 pos = 0

 for bits in range(1, tableBits + 1):
  for symbol in range(symbols):
   if lengths[symbol] == bits:
    if pos + bitMask > tableMask:
     raise Exception('Huffman table overrun')
    for leaf in range(pos, pos + bitMask):
     table[leaf] = symbol
    pos += bitMask
  bitMask >>= 1

 if pos == tableMask:
  return table

 for leaf in range(pos, tableMask):
  table[leaf] = 0xffff

 nextSymbol = max(tableMask >> 1, symbols)
 pos <<= 16
 tableMask <<= 16
 bitMask = 1 << 15

 for bits in range(tableBits + 1, lzxMaxBits + 1):
  for symbol in range(symbols):
   if lengths[symbol] == bits:
    if pos >= tableMask:
     raise Exception('Huffman table overflow')
    leaf = pos >> 16
    for bit in range(bits - tableBits):
     if table[leaf] == 0xffff:
      table[nextSymbol << 1] = 0xffff
      table[(nextSymbol << 1) + 1] = 0xffff
      table[leaf] = nextSymbol
      nextSymbol += 1
     leaf = (table[leaf] << 1) | ((pos >> (15 - bit)) & 1)
    table[leaf] = symbol
    pos += bitMask
  bitMask >>= 1

 if pos != tableMask:
  raise Exception('Incomplete huffman table')

 return table

def makeDecodeTableMaybeEmpty(symbols, tableBits, lengths):
 """Like makeDecodeTable, but tolerates a tree without any symbols at all"""
 try:
  return makeDecodeTable(symbols, tableBits, lengths)
 except Exception:
  if any(lengths[:symbols]):
   raise
  return None

def translateE8(frame, offset, filesize):
 """Undoes the translation of x86 call targets to absolute addresses"""
 out = bytearray(frame)
 pos = 0
 end = len(out) - 10

 while pos < end:
  if out[pos] != 0xe8:
   pos += 1
   continue
  current = offset + pos
  absolute = int.from_bytes(out[pos+1:pos+5], 'little', signed=True)
  if -current <= absolute < filesize:
   relative = absolute - current if absolute >= 0 else absolute + filesize
   out[pos+1:pos+5] = (relative & 0xffffffff).to_bytes(4, 'little')
  pos += 5

 return bytes(out)

def inflateLzx(chunks, windowBits, size):
 """Decodes an LZX compressed stream and yields the uncompressed frames"""
 if not 15 <= windowBits <= 21:
  raise Exception('Unsupported window size')

 windowSize = 1 << windowBits
 window = bytearray(windowSize)
 windowPos = 0
 framePos = 0
 frame = 0
 offset = 0

 mainSymbols = lzxNumChars + (lzxPositionSlots[windowBits - 15] << 3)
 mainLengths = [0] * (lzxMaintreeSymbols + lzxLenTableSafety)
 lengthLengths = [0] * (lzxLengthSymbols + lzxLenTableSafety)
 alignedLengths = [0] * (lzxAlignedSymbols + lzxLenTableSafety)
 mainTable = None
 lengthTable = None
 alignedTable = None

 r0 = r1 = r2 = 1
 blockType = 0
 blockLength = 0
 blockRemaining = 0
 intelFilesize = 0
 intelStarted = False

 data = b''
 dataPos = 0
 dataEnded = False
 bitBuf = 0
 bitCount = 0

 def fillBuffer(count):
  nonlocal data, dataPos, dataEnded
  while len(data) - dataPos < count:
   try:
    chunk = next(chunks)
   except StopIteration:
    if dataEnded:
     raise Exception('Out of input bytes')
    dataEnded = True
    chunk = b'\0\0'
   data = data[dataPos:] + chunk
   dataPos = 0

 def ensureBits(count):
  nonlocal bitBuf, bitCount, dataPos
  while bitCount < count:
   if dataPos + 2 > len(data):
    fillBuffer(2)
   bitBuf = (bitBuf << 16) | (data[dataPos+1] << 8) | data[dataPos]
   dataPos += 2
   bitCount += 16

 def readBits(count):
  nonlocal bitBuf, bitCount
  if count == 0:
   return 0
  ensureBits(count)
  bitCount -= count
  value = bitBuf >> bitCount
  bitBuf &= (1 << bitCount) - 1
  return value

 def readSymbol(table, lengths, symbols, tableBits):
  nonlocal bitBuf, bitCount
  ensureBits(lzxMaxBits)
  bits = bitBuf >> (bitCount - lzxMaxBits)
  symbol = table[bits >> (lzxMaxBits - tableBits)]
  if symbol >= symbols:
   bit = tableBits
   while symbol >= symbols:
    if bit >= lzxMaxBits:
     raise Exception('Invalid huffman symbol')
    symbol = table[(symbol << 1) | ((bits >> (lzxMaxBits - 1 - bit)) & 1)]
    bit += 1
  bitCount -= lengths[symbol]
  bitBuf &= (1 << bitCount) - 1
  return symbol

 def readBytes(count):
  nonlocal dataPos
  if dataPos + count > len(data):
   fillBuffer(count)
  chunk = data[dataPos:dataPos+count]
  dataPos += count
  return chunk

 def readLengths(lengths, first, last):
  pretreeLengths = [readBits(4) for i in range(lzxPretreeSymbols)]
  pretreeTable = makeDecodeTable(lzxPretreeSymbols, lzxPretreeTableBits, pretreeLengths)

  pos = first
  while pos < last:
   symbol = readSymbol(pretreeTable, pretreeLengths, lzxPretreeSymbols, lzxPretreeTableBits)
   if symbol == 17:
    for i in range(readBits(4) + 4):
     lengths[pos] = 0
     pos += 1
   elif symbol == 18:
    for i in range(readBits(5) + 20):
     lengths[pos] = 0
     pos += 1
   elif symbol == 19:
    run = readBits(1) + 4
    symbol = readSymbol(pretreeTable, pretreeLengths, lzxPretreeSymbols, lzxPretreeTableBits)
    length = (lengths[pos] - symbol) % 17
    for i in range(run):
     lengths[pos] = length
     pos += 1
   else:
    lengths[pos] = (lengths[pos] - symbol) % 17
    pos += 1

 if readBits(1):
  intelFilesize = (readBits(16) << 16) | readBits(16)

 while offset < size:
  frameSize = min(lzxFrameSize, size - offset)
  todo = framePos + frameSize - windowPos

  while todo > 0:
   if blockRemaining == 0:
    if blockType == lzxBlockTypeUncompressed and blockLength & 1:
     readBytes(1)

    blockType = readBits(3)
    blockLength = (readBits(16) << 8) | readBits(8)
    blockRemaining = blockLength

    if blockType == lzxBlockTypeAligned or blockType == lzxBlockTypeVerbatim:
     if blockType == lzxBlockTypeAligned:
      alignedLengths = [readBits(3) for i in range(lzxAlignedSymbols)]
      alignedTable = makeDecodeTable(lzxAlignedSymbols, lzxAlignedTableBits, alignedLengths)
     readLengths(mainLengths, 0, lzxNumChars)
     readLengths(mainLengths, lzxNumChars, mainSymbols)
     mainTable = makeDecodeTable(lzxMaintreeSymbols, lzxMaintreeTableBits, mainLengths)
     if mainLengths[0xe8] != 0:
      intelStarted = True
     readLengths(lengthLengths, 0, lzxLengthSymbols - 1)
     lengthTable = makeDecodeTableMaybeEmpty(lzxLengthSymbols, lzxLengthTableBits, lengthLengths)
    elif blockType == lzxBlockTypeUncompressed:
     intelStarted = True
     if bitCount == 0:
      ensureBits(lzxMaxBits)
     bitBuf = 0
     bitCount = 0
     r0 = int.from_bytes(readBytes(4), 'little')
     r1 = int.from_bytes(readBytes(4), 'little')
     r2 = int.from_bytes(readBytes(4), 'little')
    else:
     raise Exception('Unknown block type')

   run = min(blockRemaining, todo)
   todo -= run
   blockRemaining -= run

   if blockType == lzxBlockTypeUncompressed:
    while run > 0:
     if dataPos >= len(data):
      fillBuffer(1)
     count = min(run, len(data) - dataPos)
     window[windowPos:windowPos+count] = data[dataPos:dataPos+count]
     dataPos += count
     windowPos += count
     run -= count
   else:
    while run > 0:
     symbol = readSymbol(mainTable, mainLengths, lzxMaintreeSymbols, lzxMaintreeTableBits)

     if symbol < lzxNumChars:
      window[windowPos] = symbol
      windowPos += 1
      run -= 1
      continue

     symbol -= lzxNumChars
     matchLength = symbol & lzxNumPrimaryLengths
     if matchLength == lzxNumPrimaryLengths:
      if lengthTable is None:
       raise Exception('Length tree is empty')
      matchLength += readSymbol(lengthTable, lengthLengths, lzxLengthSymbols, lzxLengthTableBits)
     matchLength += lzxMinMatch

     slot = symbol >> 3
     if slot == 0:
      matchOffset = r0
     elif slot == 1:
      matchOffset = r1
      r1 = r0
      r0 = matchOffset
     elif slot == 2:
      matchOffset = r2
      r2 = r0
      r0 = matchOffset
     else:
      extra = lzxExtraBits[slot]
      matchOffset = lzxPositionBase[slot] - 2
      if extra >= 3 and blockType == lzxBlockTypeAligned:
       if extra > 3:
        matchOffset += readBits(extra - 3) << 3
       matchOffset += readSymbol(alignedTable, alignedLengths, lzxAlignedSymbols, lzxAlignedTableBits)
      elif extra:
       matchOffset += readBits(extra)
      r2 = r1
      r1 = r0
      r0 = matchOffset

     if windowPos + matchLength > windowSize:
      raise Exception('Match ran over window wrap')

     if matchOffset > windowPos:
      src = windowSize - (matchOffset - windowPos)
      for i in range(matchLength):
       window[windowPos+i] = window[src]
       src += 1
       if src == windowSize:
        src = 0
     elif matchOffset >= matchLength:
      src = windowPos - matchOffset
      window[windowPos:windowPos+matchLength] = window[src:src+matchLength]
     else:
      repeated = bytes(window[windowPos-matchOffset:windowPos])
      repeated *= matchLength // matchOffset + 1
      window[windowPos:windowPos+matchLength] = repeated[:matchLength]

     windowPos += matchLength
     run -= matchLength

   if run < 0:
    if -run > blockRemaining:
     raise Exception('Match ran over end of block')
    blockRemaining += run
    todo += run

  if windowPos - framePos != frameSize:
   raise Exception('Decoded beyond frame limits')

  if bitCount > 0:
   ensureBits(lzxMaxBits)
  if bitCount & 15:
   readBits(bitCount & 15)

  contents = bytes(window[framePos:framePos+frameSize])
  if intelStarted and intelFilesize and frame < 32768 and frameSize > 10:
   contents = translateE8(contents, offset, intelFilesize)
  yield contents

  offset += frameSize
  framePos += frameSize
  frame += 1

  if windowPos == windowSize:
   windowPos = 0
  if framePos == windowSize:
   framePos = 0
