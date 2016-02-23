"""A very simple parser for Windows Portable Executable (PE) files"""

from ..util import *

DosHeader = Struct('DosHeader', [
 ('magic', Struct.STR % 2),
 ('...', 58),
 ('peHeaderOffset', Struct.INT32),
])
dosHeaderMagic = 'MZ'

PeHeader = Struct('PeHeader', [
 ('magic', Struct.STR % 4),
 ('...', 2),
 ('numSections', Struct.INT16),
 ('...', 12),
 ('optionalSize', Struct.INT16),
 ('...', 2),
])
peHeaderMagic = 'PE\x00\x00'

SectionHeader = Struct('SectionHeader', [
 ('type', Struct.STR % 8),
 ('...', 8),
 ('size', Struct.INT32),
 ('offset', Struct.INT32),
 ('...', 16),
])

def isExe(data):
 return len(data) >= DosHeader.size and DosHeader.unpack(data).magic == dosHeaderMagic

def readExe(data):
 """Takes the contents of a PE file and returns a dict containing the name and content of all sections"""
 dosHeader = DosHeader.unpack(data)
 if dosHeader.magic != dosHeaderMagic:
  raise Exception('Wrong magic')

 peHeader = PeHeader.unpack(data, dosHeader.peHeaderOffset)
 if peHeader.magic != peHeaderMagic:
  raise Exception('Wrong magic')

 sections = {}
 for i in xrange(peHeader.numSections):
  section = SectionHeader.unpack(data, dosHeader.peHeaderOffset + PeHeader.size + peHeader.optionalSize + i * SectionHeader.size)
  sections[section.type] = memoryview(data)[section.offset:section.offset+section.size]

 return sections
