#!/usr/bin/env python

from distutils.core import setup
from ldoce5viewer import __version__


def iter_static():
    import os, os.path

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


#--------
# py2exe
#--------
try:
    import py2exe
except ImportError:
    pass
else:
    extra_options.update(dict(
        windows = [{
            'script': 'ldoce5viewer.py',
            'icon_resources': [(1, 'ldoce5viewer/resources/ldoce5viewer.ico')],
        }],
        options = {'py2exe': {
            'includes': ['sip'],
            'packages': ['lxml.etree', 'gzip', 'lxml._elementpath'],
            #'excludes': ['_ssl', 'ssl', 'bz2', 'sqlite3', 'select',
            #             'xml', 'unittest', 'email', 'distutils', 'xmlrpclib',
            #             'doctest', 'pdb', 'tarfile'],
            'compressed': True,
            'optimize': 2,
            'bundle_files': 3,
            'dist_dir': 'exedist',
            }},
        zipfile=None
        ))


#------------
# setup(...)
#------------
setup(
    name = 'ldoce5viewer',
    version = __version__,
    description = 'LDOCE5 Viewer',
    url = 'http://hakidame.net/ldoce5viewer/',
    license = 'GPLv3+',
    platforms='any',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Development Status :: 5 - Production/Stable'
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Education',
        'Programming Language :: Python',
        'Operating System :: OS Independent',
        'Topic :: Education',
        ],
    author = 'Taku Fukada',
    author_email = 'naninunenor@gmail.com',
    package_dir = {'ldoce5viewer': 'ldoce5viewer'},
    packages = [
        'ldoce5viewer',
        'ldoce5viewer.qtgui',
        'ldoce5viewer.qtgui.ui',
        'ldoce5viewer.qtgui.resources',
        'ldoce5viewer.qtgui.utils',
        'ldoce5viewer.qtgui.utils.mp3play',
        'ldoce5viewer.utils',
        'ldoce5viewer.ldoce5',
        'ldoce5viewer.whoosh',
        'ldoce5viewer.whoosh.lang',
        'ldoce5viewer.whoosh.support',
        'ldoce5viewer.whoosh.filedb',
        'ldoce5viewer.whoosh.qparser',
        'ldoce5viewer.whoosh.query',
        'ldoce5viewer.whoosh.analysis',
        ],
    package_data = {'ldoce5viewer': list(iter_static())},
    scripts = ['scripts/ldoce5viewer'],
    **extra_options
)

