"""Parser for the .dat file contained in the updater executable"""

import re

import constants
from ..util import *

def findDat(paths):
 """Guesses the .dat file from a list of filenames"""
 return [path for path in paths if re.search('/FirmwareData_([^/]+)\.dat$', path)][0]

def readDat(data):
 """Takes the contents of the .dat file and returns a dict containing the name and content of its chunks"""
 if data[:8] != constants.datHeader:
  raise Exception('Wrong header')

 chunks = {}
 offset = 8
 while 'DEND' not in chunks:
  length = parse32be(data[offset:offset+4])
  type = data[offset+4:offset+8]
  chunks[type] = data[offset+8:offset+8+length]
  offset += 8 + length

 if crc32(data[:offset-12]) != parse32be(chunks['DEND']):
  raise Exception('Wrong checksum')

 return chunks
