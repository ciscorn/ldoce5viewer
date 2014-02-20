LDOCE5 Viewer
=============

The LDOCE5 Viewer is an alternative dictionary viewer for the Longman Dictionary of Contemporary English 5th Edition (LDOCE 5).

Website: http://hakidame.net/ldoce5viewer/

It runs on Linux and Microsoft Windows.

This software is free and open source software licensed under the terms of GPLv3.


Prerequisites
-------------

* Longman Dictionary of Contemporary English 5th Edition (DVD-ROM)

* Python 2.7 or 2.6 (or 3.x)

* PyQt

    - `python-qt4` (Ubuntu/Mint/Debian), `python-pyqt5` (Arch Linux)

* lxml

    - `python-lxml` (Ubuntu/Mint/Debian), `python-lxml` (Arch Linux)

* Whoosh 2.x

    - `python-whoosh` (Ubuntu/Mint/Debian), `python-whoosh` in AUR (Arch Linux)

* [On Linux] Python bindings for Gstreamer

    - `python-gst0.10` (Ubuntu/Mint/Debian), `gst-python` (Arch Linux)

* [On Linux] Gstreamer plugins for MP3 audio playback

    - `gstreader0.10-plugins-good` & `gstreamer0.10-plugins-ugly` (Ubuntu/Mint/Debian), `gst-plugins-good` & `gst-plugins-ugly` (Arch Linux)


Installation
------------

###Linux

####Packages

For Arch Linux, two packages [ldoce5viewer](https://aur.archlinux.org/packages/ldoce5viewer/) and [ldoce5viewer-git](https://aur.archlinux.org/packages/ldoce5viewer-git/) exist on AUR.

####Manually

1. Enter the following commands in the terminal:

```bash
$ make build
$ sudo make install
```

2. Copy the 'ldoce5.data' directory from the LDOCE5 DVD-ROM to an arbitrary location in your HDD or SSD.

3. Start the LDOCE5 Viewer.

4. The application will ask you the location where you put 'ldoce5.data'.

###Mac OS X

(for advanced users)

1. Install MacPorts

2. Install the following ports:

    - python27 (or python3x)
    - py27-pyqt4
    - py27-lxml
    - py27-whoosh
    - py27-pyobjc-cocoa

3. Run the LDOCE5 Viewer

