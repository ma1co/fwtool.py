"""A very simple parser for Windows Portable Executable (PE) files"""

from collections import OrderedDict

from ..io import FilePart
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

def isExe(file):
 header = DosHeader.unpack(file)
 return header and header.magic == dosHeaderMagic

def readExe(file):
 """Takes the a PE file and returns a dict containing the sections"""
 dosHeader = DosHeader.unpack(file)
 if dosHeader.magic != dosHeaderMagic:
  raise Exception('Wrong magic')

 peHeader = PeHeader.unpack(file, dosHeader.peHeaderOffset)
 if peHeader.magic != peHeaderMagic:
  raise Exception('Wrong magic')

 sections = OrderedDict()
 for i in xrange(peHeader.numSections):
  section = SectionHeader.unpack(file, dosHeader.peHeaderOffset + PeHeader.size + peHeader.optionalSize + i * SectionHeader.size)
  sections[section.type] = FilePart(file, section.offset, section.size)

 return sections
