#!/usr/bin/env python
"""A command line application to unpack Sony camera firmware images, based on fwtool by oz_paulb / nex-hack"""

import argparse
import os
import shutil
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
 for file in files:
  fn = path + file.path
  if S_ISDIR(file.mode):
   mkdirs(fn)
  elif S_ISREG(file.mode):
   mkdirs(os.path.dirname(fn))
   with open(fn, 'w+b') as dstFile:
    file.extractTo(dstFile)
    if archive.isArchive(dstFile):
     print 'Unpacking %s' % fn
     writeFileTree(archive.readArchive(dstFile), fn + '_unpacked')

 # Set mtimes:
 for file in files:
  fn = path + file.path
  if S_ISDIR(file.mode) or S_ISREG(file.mode):
   setmtime(fn, file.mtime)

def unpackCommand(file, outDir):
 """Extracts the firmware image from the updater executable, unpacks it and extracts it to the specified directory"""
 mkdirs(outDir)

 print 'Reading installer binary'
 exeSectors = pe.readExe(file)

 print 'Decompressing installer data'
 zipFile = exeSectors['_winzip_']
 zippedFiles = dict((file.path, file) for file in zip.readZip(zipFile))

 print 'Reading .dat file'
 datFile = open(outDir + '/firmware.dat', 'w+b')
 zippedDatFile = zippedFiles[dat.findDat(zippedFiles.keys())]
 zippedDatFile.extractTo(datFile)
 mtime = zippedDatFile.mtime
 datChunks = dat.readDat(datFile)

 print 'Decoding firmware image'
 fdatFile = open(outDir + '/firmware.fdat', 'w+b')
 encryptedFdatFile = datChunks['FDAT']
 fdat.decryptFdat(encryptedFdatFile, fdatFile)
 fdatContents = fdat.readFdat(fdatFile)

 def toUnixFile(path, file):
  return archive.UnixFile(
   path = path,
   size = -1,
   mtime = mtime,
   mode = S_IFREG,
   uid = 0,
   gid = 0,
   extractTo = lambda dstFile: shutil.copyfileobj(file, dstFile)
  )

 print 'Extracting files'
 writeFileTree([
  toUnixFile('/firmware.tar', fdatContents.tar),
  toUnixFile('/updater.img', fdatContents.img),
 ], outDir)

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
