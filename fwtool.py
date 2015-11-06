#!/usr/bin/env python
"""A command line application to unpack Sony camera firmware images, based on fwtool by oz_paulb / nex-hack"""

import argparse
import os
import re

from fwtool import lzpt, pe, tar, zip
from fwtool.sony import dat, fdat

def writeFile(dir, path, data):
 """Writes data to dir/path"""
 fn = os.path.join(dir, path)
 try:
  os.makedirs(os.path.dirname(fn))
 except OSError:
  pass
 with open(fn, 'wb') as f:
  f.write(data)

def unpackCommand(file, outDir):
 """Extracts the firmware image from the updater executable, unpacks it and extracts it to the specified directory"""
 print 'Reading installer binary'
 exeFile = pe.readExe(file.read())

 print 'Decompressing installer data'
 zipFile = zip.readZip(zip.findZip(exeFile['_winzip_'].tobytes()))

 print 'Reading .dat file'
 datFile = dat.readDat(zipFile[dat.findDat(zipFile.keys())])

 print 'Decoding firmware image'
 firmwareData = fdat.decryptFdat(datFile['FDAT'].tobytes())

 print 'Extracting updater image'
 writeFile(outDir, 'updater.img', firmwareData.getImg())

 print 'Decompressing .tar file'
 tarFile = tar.readTar(firmwareData.getTar())

 print 'Extracting files'
 for path, data in tarFile.iteritems():
  if not re.search('^\d{4}_([^/]+)_sum/\\1\.sum$', path):
   if path.startswith('0700_part_image/dev/nflash') and lzpt.isLzpt(data):
    print 'Decompressing file system image ' + os.path.basename(path)
    data = lzpt.readLzpt(data)
   writeFile(outDir, path, data)

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
