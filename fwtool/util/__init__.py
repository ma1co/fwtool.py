"""Some utility functions to unpack integers"""

import binascii
import struct

def parse32be(data):
 return struct.unpack('>I', data)[0]

def parse32le(data):
 return struct.unpack('<I', data)[0]

def parse16be(data):
 return struct.unpack('>H', data)[0]

def parse16le(data):
 return struct.unpack('<H', data)[0]

def parse16leArr(data):
 return struct.unpack('<%sH' % str(len(data) / 2), data)

def crc32(data):
 return binascii.crc32(data) & 0xffffffff
