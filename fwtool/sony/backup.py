"""A parser for Backup.bin, the settings file used on Sony cameras"""
# see /usr/kmod/backup.ko

from collections import namedtuple

from ..util import *

BackupHeader = Struct('BackupHeader', [
 ('magic', Struct.INT32),
 ('cookie', Struct.INT32),
 ('writeComp', Struct.INT32),
 ('version', Struct.STR % 4),
 ('numSubsystems', Struct.INT32),
])
backupHeaderMagic = [0x82ec0000, 0x832c0000]

SubsystemTableEntry = Struct('SubsystemTableEntry', [
 ('numProperties', Struct.INT16),
 ('ptr', Struct.INT32),
])

PropertyTableEntryV1 = Struct('PropertyTableEntryV1', [
 ('attr', Struct.INT8),
 ('ptr', Struct.INT32),
])

PropertyTableEntryV4 = Struct('PropertyTableEntryV4', [
 ('attr', Struct.INT16),
 ('ptr', Struct.INT32),
])

OversizeProperty = Struct('OversizeProperty', [
 ('size', Struct.INT16),
])

VariableSizeProperty = Struct('VariableSizeProperty', [
 ('size', Struct.INT16),
 ('maxSize', Struct.INT16),
])

BackupProperty = namedtuple('BackupProperty', 'id, attr, data, resetData')

def readBackup(file):
 header = BackupHeader.unpack(file)

 if header.magic not in backupHeaderMagic:
  raise Exception('Wrong magic')
 if header.version[:2] != b'BK':
  raise Exception('Wrong version number')
 version = int(header.version[2:3])

 headerLength = 0x100 if version >= 2 else 0x20
 PropertyTableEntry = PropertyTableEntryV4 if version >= 4 else PropertyTableEntryV1

 subsystemTableOffset = headerLength
 propertyTableOffset = subsystemTableOffset + header.numSubsystems * SubsystemTableEntry.size

 for i in range(header.numSubsystems):
  subsystem = SubsystemTableEntry.unpack(file, subsystemTableOffset + i * SubsystemTableEntry.size)

  for j in range(subsystem.numProperties):
   id = i << 16 | j
   property = PropertyTableEntry.unpack(file, propertyTableOffset + (subsystem.ptr + j) * PropertyTableEntry.size)

   if property.ptr == 0xffffffff:
    continue

   attr = property.attr
   size = property.ptr >> 24
   offset = property.ptr & 0xffffff
   maxSize = size

   if size == 0xff:
    op = OversizeProperty.unpack(file, offset)
    size = op.size
    maxSize = op.size
    offset += OversizeProperty.size
   elif size == 0:
    vp = VariableSizeProperty.unpack(file, offset)
    size = vp.size
    maxSize = vp.maxSize
    offset += VariableSizeProperty.size

   file.seek(offset)
   data = file.read(size)
   resetData = None

   if attr & 0x01:# property is read only, cannot be written with Backup_write()
    pass
   if attr & 0x02:# property is protected, won't be changed by Backup_protect()
    pass
   if attr & 0x08:# callbacks are triggered when this property is written with Backup_write()
    pass
   if attr & 0x74:# property can be reset with Backup_reset()
    file.seek(offset + maxSize)
    resetData = file.read(size)
   if attr & 0x80:# property data is an array that can be read with Backup_read_setting_attr()
    # there are ord(backupProperties[0x3e000c].data)+1 elements in the array
    pass

   yield BackupProperty(id, attr, data, resetData)
