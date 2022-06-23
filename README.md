# fwtool.py #

A tool to unpack Sony camera firmware images, originally ported from [nex-hack's fwtool](http://www.personal-view.com/faqs/sony-hack/fwtool).

## Camera Compatibility ###
The following firmware types can be extracted:

* **"FDAT" firmware updates**
  * **CXD90045**: ILCE-7M3, ILCE-6600, …
  * **CXD90014**: ILCE-7, ILCE-6000, ...
  * **CXD4132**: DSC-RX100, NEX-6, …
  * **CXD4120**
  * **CXD4115**: DSC-HX5V, NEX-3, SLT-A33, ...
  * **CXD4105 / MB8AC102**

* **"Msfirm" firmware updates**
  * **CXD4108**: DSC-T100, DSC-G3
  * **CXD4105**: HDR-SR1, HDR-UX1, DSC-G1

* **DSLR firmware updates**
  * DSLR-A230, DSLR-A700, ...

* **"ASH" firmware updates**
  * DSC-V1, DSC-F828, DSC-H2, ...

## Usage ##
Download the [latest release](https://github.com/ma1co/fwtool.py/releases/latest) (Windows or OS X) or clone this repository. Run `fwtool --help` for more information.

### Unpack a firmware image ###
    fwtool unpack -f Update_ILCE_V100.exe -o outDir

The following files are accepted as input (*-f* flag):
* A Windows firmware updater executable (.exe file)
* The *FirmwareData.dat* file extracted from an updater
* A firmware dump created by running `dd if=/dev/nflasha of=dump.dat` on the camera

### Decode Backup.bin ###
    fwtool print_backup -f Backup.bin

This will list all properties defined in Backup.bin, the settings file used on Sony cameras. In firmware updates, you can find different variants this file in the *0110_backup* directory.
