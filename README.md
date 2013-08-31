LDOCE5 Viewer
=============

The LDOCE5 Viewer is an alternative dictionary viewer for the Longman Dictionary of Contemporary English 5th Edition (LDOCE 5).

It runs on Linux and Microsoft Windows.

This software is free and open source software licensed under the terms of GPLv3.

Website: http://hakidame.net/ldoce5viewer/


Prerequisites
=============

* Python 2.7 or 2.6 (not 3.x)

* PyQt

    - `python-qt4` (in Ubuntu/Mint/Debian)
    - `python2-pyqt` (in Arch Linux)

* lxml

    - `python-lxml` (in Ubuntu/Mint/Debian)
    - `python2-lxml` (in Arch Linux)

* [On Linux] Python bindings for Gstreamer

    - `python-gst` (in Ubuntu/Mint/Debian)
    - `gstreamer0.10-python` (in Arch Linux)


Installation
============

Linux
-----

1. Enter the following commands in the terminal:

```bash
$ sudo python2.7 ./setup.py install --optimize
$ sudo cp ./ldoce5viewer.desktop /usr/share/applications/
$ sudo cp ./ldoce5viewer/qtgui/resources/ldoce5viewer.svg /usr/share/pixmaps/
$ [ -x /usr/bin/update-desktop-database ] && sudo update-desktop-database -q
```

2. Copy the 'ldoce5.data' directory from the LDOCE5 DVD-ROM to an arbitrary location in your HDD or SSD.

3. Start the LDOCE5 Viewer.

4. The application will ask you the location where you put 'ldoce5.data'.


Terms and Conditions
====================

Copyright (c) 2012-2013 Taku Fukada

This software is licensed under the GPLv3.

Discraimer
----------

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

