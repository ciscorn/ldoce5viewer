#!/usr/bin/env python

import subprocess
from distutils.core import setup

from ldoce5viewer import __version__


def iter_static():
    import os
    import os.path

    for root, dirs, files in os.walk("ldoce5viewer/static"):
        for filename in files:
            yield os.path.relpath(os.path.join(root, filename), "ldoce5viewer")

    for root, dirs, files in os.walk("ldoce5viewer/qtgui/resources"):
        for filename in files:
            yield os.path.relpath(os.path.join(root, filename), "ldoce5viewer")

    for root, dirs, files in os.walk("ldoce5viewer/qtgui/ui"):
        for filename in files:
            yield os.path.relpath(os.path.join(root, filename), "ldoce5viewer")


extra_options = {}


# --------
# py2exe
# --------
try:
    import py2exe
except ImportError:
    pass
else:
    extra_options.update(
        dict(
            name="LDOCE5 Viewer",
            windows=[
                {
                    "script": "ldoce5viewer.py",
                    "icon_resources": [(1, "ldoce5viewer/resources/ldoce5viewer.ico")],
                }
            ],
            options={
                "py2exe": {
                    "includes": ["sip"],
                    "packages": ["lxml.etree", "gzip", "lxml._elementpath"],
                    #'excludes': ['_ssl', 'ssl', 'bz2', 'sqlite3', 'select',
                    #             'xml', 'unittest', 'email', 'distutils', 'xmlrpclib',
                    #             'doctest', 'pdb', 'tarfile'],
                    "compressed": True,
                    "optimize": 2,
                    "bundle_files": 3,
                    "dist_dir": "exedist",
                }
            },
            zipfile=None,
        )
    )


# --------
# py2app
# --------
try:
    import py2app
except ImportError:
    pass
else:
    qt_plugins_path = subprocess.check_output(
        "qmake -query QT_INSTALL_PLUGINS", shell=True
    )
    qt_plugins_path = qt_plugins_path[0 : len(qt_plugins_path) - 1]  # remove "\n"
    extra_options.update(
        dict(
            name="LDOCE5 Viewer",
            app=["ldoce5viewer.py"],
            options={
                "py2app": {
                    "iconfile": "./ldoce5viewer/qtgui/resources/ldoce5viewer.icns",
                    "argv_emulation": False,
                    "optimize": 0,
                    "includes": ["sip", "lxml._elementpath"],
                    "packages": [],
                    "excludes": [
                        "email",
                        "sqlite3",
                        "PyQt5.QtCLucene",
                        "PyQt5.QtHtml",
                        "PyQt5.QtHelp",
                        "PyQt5.QtTest",
                        "PyQt5.QtOpenGL",
                        "PyQt5.QtScript",
                        "PyQt5.QtScriptTools",
                        "PyQt5.QtSql",
                        "PyQt5.QtDeclarative",
                        "PyQt5.QtMultimedia",
                        "PyQt5.QtDesigner",
                        "PyQt5.QtXml",
                        "PyQt5.QtXmlPatterns",
                    ],
                    #'qt_plugins': [
                    #    'imageformats/libqjpeg.dylib',
                    # ]
                }
            },
            data_files=[
                ("qt_plugins/imageformats", [qt_plugins_path]),
                ("", ["ldoce5viewer/static"]),
            ],
        )
    )


# ------------
# setup(...)
# ------------

if "name" not in extra_options:
    extra_options["name"] = "ldoce5viewer"

setup(
    version=__version__,
    description="LDOCE5 Viewer",
    url="https://forward-backward.co.jp/ldoce5viewer/",
    license="GPLv3+",
    platforms="any",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Development Status :: 5 - Production/Stable"
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Education",
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Topic :: Education",
    ],
    author="Taku Fukada",
    author_email="naninunenor@gmail.com",
    package_dir={"ldoce5viewer": "ldoce5viewer"},
    packages=[
        "ldoce5viewer",
        "ldoce5viewer.qtgui",
        "ldoce5viewer.qtgui.ui",
        "ldoce5viewer.qtgui.resources",
        "ldoce5viewer.qtgui.utils",
        "ldoce5viewer.qtgui.utils.mp3play",
        "ldoce5viewer.utils",
        "ldoce5viewer.ldoce5",
    ],
    package_data={"ldoce5viewer": list(iter_static())},
    scripts=["scripts/ldoce5viewer"],
    **extra_options
)
