#!/usr/bin/env python
"""A command line application to unpack Sony camera firmware images, based on fwtool by oz_paulb / nex-hack"""

import argparse
import os
import re
from stat import *

from fwtool import archive, pe, zip
from fwtool.sony import dat, fdat

def mkdirs(path):
 try:
  os.makedirs(path)
 except OSError:
  pass

def setmtime(path, time):
 os.utime(path, (time, time))

def writeFileTree(files, path):
 """Writes a dict of UnixFiles to the disk, unpacking known archive files"""
 for fn, file in files.iteritems():
  fn = path + fn
  if S_ISDIR(file.mode):
   mkdirs(fn)
  elif S_ISREG(file.mode):
   mkdirs(os.path.dirname(fn))
   with open(fn, 'wb') as f:
    f.write(file.contents)
   if archive.isArchive(file.contents):
    print 'Unpacking %s' % fn
    writeFileTree(archive.readArchive(file.contents), fn + '_unpacked')

 # Set mtimes:
 for fn, file in files.iteritems():
  fn = path + fn
  if S_ISDIR(file.mode) or S_ISREG(file.mode):
   setmtime(fn, file.mtime)

def unpackCommand(file, outDir):
 """Extracts the firmware image from the updater executable, unpacks it and extracts it to the specified directory"""
 print 'Reading installer binary'
 exeFile = pe.readExe(file.read())

 print 'Decompressing installer data'
 zipFile = zip.readZip(zip.findZip(exeFile['_winzip_'].tobytes()))

 print 'Reading .dat file'
 datZipFile = zipFile[dat.findDat(zipFile.keys())]
 mtime = datZipFile.mtime
 datFile = dat.readDat(datZipFile.contents)

 print 'Decoding firmware image'
 firmwareData = fdat.decryptFdat(datFile['FDAT'].tobytes())

 tarData = firmwareData.getTar()
 updaterData = firmwareData.getImg().tobytes()

 print 'Extracting files'
 writeFileTree({
  '/firmware.tar': archive.UnixFile(size = len(tarData), mtime = mtime, mode = S_IFREG, uid = 0, gid = 0, contents = tarData),
  '/updater.img': archive.UnixFile(size = len(updaterData), mtime = mtime, mode = S_IFREG, uid = 0, gid = 0, contents = updaterData),
 }, outDir)

 print 'Done'


def main():
 """Command line main"""
 parser = argparse.ArgumentParser()
 subparsers = parser.add_subparsers(dest='command', title='commands')
 install = subparsers.add_parser('unpack', description='Unpack a firmware file')
 install.add_argument('-f', dest='inFile', type=argparse.FileType('rb'), required=True, help='the updater .exe file')
 install.add_argument('-o', dest='outDir', required=True, help='output directory')

 args = parser.parse_args()
 if args.command == 'unpack':
  unpackCommand(args.inFile, args.outDir)


if __name__ == '__main__':
 main()
