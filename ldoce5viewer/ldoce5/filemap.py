"""File-location map"""

from hashlib import md5
from struct import Struct

import lxml.etree as et

from ..utils import cdb
from . import idmreader
from .utils import shorten_id

_struct_IIII = Struct("<IIII")
_pack_IIII = _struct_IIII.pack
_unpack_IIII = _struct_IIII.unpack
_struct_IHHH = Struct("<IHHH")
_pack_IHHH = _struct_IHHH.pack
_unpack_IHHH = _struct_IHHH.unpack


class FilemapReader(object):
    def __init__(self, filemap_path):
        self._filemap = cdb.CDBReader(filemap_path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._filemap.close()

    def close(self):
        self._filemap.close()

    def lookup(self, archive, name):
        key = md5((archive + ":" + name).encode("ascii")).digest()[:10]
        data = self._filemap[key]
        if len(data) == 16:
            location = _unpack_IIII(data)
        else:
            location = _unpack_IHHH(data)
        return location


class FilemapMaker(object):
    def __init__(self, f):
        self._maker = cdb.CDBMaker(f)

    def add(self, archive, name, location):
        cmpo, cmps, orgo, orgs = location
        key = md5((archive + ":" + name).encode("ascii")).digest()[:10]
        if cmps < 65536 and orgo < 65536 and orgs < 65536:
            self._maker.add(key, _pack_IHHH(cmpo, cmps, orgo, orgs))
        else:
            self._maker.add(key, _pack_IIII(cmpo, cmps, orgo, orgs))

    def finalize(self):
        self._maker.finalize()


def list_files(data_dir, arch_name):

    with idmreader.ArchiveReader(data_dir, arch_name) as arch_reader:
        files = idmreader.list_files(data_dir, arch_name)

        for (dirs, name, location) in files:
            if arch_name == "picture":
                name = "{0}/{1}".format(dirs[0], name)
            elif arch_name == "fs" or arch_name == "pronpractice":
                root = et.fromstring(arch_reader.read(location))
                name = shorten_id(root.get("id"))
            elif name.endswith(".xml"):
                root = et.fromstring(arch_reader.read(location))
                if root.get("id", None) is not None:
                    name = root.get("id")
                else:
                    name = root.get("idm_id")
            yield (name, location)
