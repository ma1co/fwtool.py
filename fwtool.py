#!/usr/bin/env python
"""A command line application to unpack Sony camera firmware images, based on fwtool by oz_paulb / nex-hack"""

import argparse
import io
import os
import shutil
from stat import *
import yaml

from fwtool import archive, pe, zip
from fwtool.sony import backup, dat, fdat, flash

def mkdirs(path):
 try:
  os.makedirs(path)
 except OSError:
  pass

def setmtime(path, time):
 os.utime(path, (time, time))

def writeFileTree(files, path):
 """Writes a list of UnixFiles to the disk, unpacking known archive files"""
 for file in files:
  fn = path + file.path
  if S_ISDIR(file.mode):
   mkdirs(fn)
  elif S_ISREG(file.mode):
   mkdirs(os.path.dirname(fn))
   with open(fn, 'w+b') as dstFile:
    shutil.copyfileobj(file.contents, dstFile)
    if archive.isArchive(dstFile):
     print 'Unpacking %s' % fn
     writeFileTree(archive.readArchive(dstFile), fn + '_unpacked')

 # Set mtimes:
 for file in files:
  fn = path + file.path
  if S_ISDIR(file.mode) or S_ISREG(file.mode):
   setmtime(fn, file.mtime)

def toUnixFile(path, file, mtime=0):
 return archive.UnixFile(
  path = path,
  size = -1,
  mtime = mtime,
  mode = S_IFREG | 0775,
  uid = 0,
  gid = 0,
  contents = file,
 )

def writeYaml(yamlData, file):
 yaml.add_representer(tuple, lambda dumper, data: dumper.represent_list(data))
 yaml.add_representer(dict, lambda dumper, data: dumper.represent_mapping(dumper.DEFAULT_MAPPING_TAG, data, flow_style=False))
 yaml.add_representer(int, lambda dumper, data: dumper.represent_int(hex(data) if data >= 10 else data))
 yaml.dump(yamlData, file)


def unpackInstaller(exeFile, datFile):
 print 'Extracting installer binary'
 exeSectors = pe.readExe(exeFile)
 zipFile = exeSectors['_winzip_']
 zippedFiles = dict((file.path, file) for file in zip.readZip(zipFile))

 zippedDatFile = zippedFiles[dat.findDat(zippedFiles.keys())]
 shutil.copyfileobj(zippedDatFile.contents, datFile)

 return zippedDatFile.mtime


def unpackDat(datFile, fdatFile):
 print 'Decrypting firmware image'
 datContents = dat.readDat(datFile)
 crypterName, data = fdat.decryptFdat(datContents.firmwareData)
 shutil.copyfileobj(data, fdatFile)

 return {
  'normalUsbDescriptors': datContents.normalUsbDescriptors,
  'updaterUsbDescriptors': datContents.updaterUsbDescriptors,
  'isLens': datContents.isLens,
  'crypterName': crypterName,
 }


def unpackFdat(fdatFile, outDir, mtime):
 print 'Extracting files'
 fdatContents = fdat.readFdat(fdatFile)

 writeFileTree([
  toUnixFile('/firmware.tar', fdatContents.firmware, mtime),
  toUnixFile('/updater.img', fdatContents.fs, mtime),
 ], outDir)

 return {
  'model': fdatContents.model,
  'region': fdatContents.region,
  'version': fdatContents.version,
  'isAccessory': fdatContents.isAccessory,
 }


def unpackDump(dumpFile, outDir, mtime):
 print 'Extracting partitions'
 writeFileTree((toUnixFile('/nflasha%d' % i, f, mtime) for i, f in flash.readPartitionTable(dumpFile)), outDir)


def unpackCommand(file, outDir):
 """Extracts the input file to the specified directory"""
 mkdirs(outDir)
 mtime = os.stat(file.name).st_mtime

 datConf = None
 fdatConf = None

 if pe.isExe(file):
  with open(outDir + '/firmware.dat', 'w+b') as datFile, open(outDir + '/firmware.fdat', 'w+b') as fdatFile:
   mtime = unpackInstaller(file, datFile)
   datConf = unpackDat(datFile, fdatFile)
   fdatConf = unpackFdat(fdatFile, outDir, mtime)
 elif dat.isDat(file):
  with open(outDir + '/firmware.fdat', 'w+b') as fdatFile:
   datConf = unpackDat(file, fdatFile)
   fdatConf = unpackFdat(fdatFile, outDir, mtime)
 elif fdat.isFdat(file):
  fdatConf = unpackFdat(file, outDir, mtime)
 elif flash.isPartitionTable(file):
  unpackDump(file, outDir, mtime)
 else:
  raise Exception('Unknown file type!')

 with open(outDir + '/config.yaml', 'wb') as yamlFile:
  writeYaml({'dat': datConf, 'fdat': fdatConf}, yamlFile)


def packCommand(firmwareFile, fsFile, bodyFile, configFile, outDir):
 mkdirs(outDir)

 config = yaml.safe_load(configFile)
 datConf = config['dat']
 fdatConf = config['fdat']

 if not fsFile and bodyFile:
  print 'Packing updater file system'
  fsFile = open(outDir + '/updater_packed.img', 'w+b')
  archive.cramfs.writeCramfs([toUnixFile('/bodylib/libupdaterbody.so', bodyFile)], fsFile)

 if fdatConf:
  print 'Creating firmware image'
  with open(outDir + '/firmware_packed.fdat', 'w+b') as fdatFile:
   fdat.writeFdat(fdat.FdatFile(
    model = fdatConf['model'],
    region = fdatConf['region'],
    version = fdatConf['version'],
    isAccessory = fdatConf['isAccessory'],
    firmware = firmwareFile if firmwareFile else io.BytesIO(),
    fs = fsFile if fsFile else io.BytesIO(),
   ), fdatFile)

   if datConf:
    print 'Encrypting firmware image'
    encrypted = fdat.encryptFdat(fdatFile, datConf['crypterName'])
    with open(outDir + '/firmware_packed.dat', 'w+b') as datFile:
     dat.writeDat(dat.DatFile(
      normalUsbDescriptors = datConf['normalUsbDescriptors'],
      updaterUsbDescriptors = datConf['updaterUsbDescriptors'],
      isLens = datConf['isLens'],
      firmwareData = encrypted,
     ), datFile)


def printHexDump(data, n=16, indent=0):
 for i in xrange(0, len(data), n):
  line = data[i:i+n]
  hex = ' '.join('%02x' % ord(c) for c in line)
  text = ''.join(c if len(repr(c)) == 3 and c != ' ' else '.' for c in line)
  print '%*s%-*s %s' % (indent, '', n*3, hex, text)


def printBackupCommand(file):
 """Prints all properties in a Backup.bin file"""
 for property in backup.readBackup(file):
  print 'id=0x%08x, size=0x%04x, attr=0x%02x:' % (property.id, len(property.data), property.attr)
  printHexDump(property.data, indent=2)
  if property.resetData and property.resetData != property.data:
   print 'reset data:'
   printHexDump(property.resetData, indent=2)
  print ''


def main():
 """Command line main"""
 parser = argparse.ArgumentParser()
 subparsers = parser.add_subparsers(dest='command', title='commands')
 unpack = subparsers.add_parser('unpack', description='Unpack a firmware file')
 unpack.add_argument('-f', dest='inFile', type=argparse.FileType('rb'), required=True, help='input file')
 unpack.add_argument('-o', dest='outDir', required=True, help='output directory')
 pack = subparsers.add_parser('pack', description='Pack a firmware file')
 pack.add_argument('-c', dest='configFile', type=argparse.FileType('rb'), required=True, help='configuration file (config.yaml)')
 packBody = pack.add_mutually_exclusive_group()
 packBody.add_argument('-u', dest='updaterFile', type=argparse.FileType('rb'), help='updater file (updater.img)')
 packBody.add_argument('-b', dest='updaterBodyFile', type=argparse.FileType('rb'), help='updater body file (libupdaterbody.so)')
 pack.add_argument('-f', dest='firmwareFile', type=argparse.FileType('rb'), help='firmware file (firmware.tar)')
 pack.add_argument('-o', dest='outDir', required=True, help='output directory')
 printBackup = subparsers.add_parser('print_backup', description='Print the contents of a Backup.bin file')
 printBackup.add_argument('-f', dest='backupFile', type=argparse.FileType('rb'), required=True, help='backup file')

 args = parser.parse_args()
 if args.command == 'unpack':
  unpackCommand(args.inFile, args.outDir)
 elif args.command == 'pack':
  packCommand(args.firmwareFile, args.updaterFile, args.updaterBodyFile, args.configFile, args.outDir)
 elif args.command == 'print_backup':
  printBackupCommand(args.backupFile)


if __name__ == '__main__':
 main()
