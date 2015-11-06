"""A very simple parser for Windows Portable Executable (PE) files"""

from ..util import *

def readExe(data):
 """Takes the contents of a PE file and returns a dict containing the name and content of all sections"""
 ntOffset = parse32le(data[60:64])

 optOffset = ntOffset + 24
 optLen = parse16le(data[ntOffset+20:ntOffset+22])

 sectOffset = optOffset + optLen
 sectNum = parse16le(data[ntOffset+6:ntOffset+8])
 sectLen = 40

 sections = {}
 offset = sectOffset
 for i in xrange(0, sectNum):
  sectData = data[offset:offset+sectLen]
  type = sectData[:8]
  size = parse32le(sectData[16:20])
  off = parse32le(sectData[20:24])
  sections[type] = memoryview(data)[off:off+size]
  offset += sectLen

 return sections
