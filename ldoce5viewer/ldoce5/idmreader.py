'''Archive reader for IDM's format'''

from __future__ import absolute_import

import os.path
from struct import unpack
from zlib import decompress
try:
    from configparser import SafeConfigParser
except:
    from ConfigParser import SafeConfigParser

try:
    import __builtin__
    range = __builtin__.xrange
except ImportError:
    pass

import itertools
zip = getattr(itertools, 'izip', zip)

_IDM_TYPE_SIZES = {'UBYTE': 1, 'USHORT': 2, 'U24': 3, 'ULONG': 4}

_ARCHIVE_DIRS = dict(
    etymologies='etymologies.skn',
    word_families='word_families.skn',
    examples='examples.skn',
    sound='sound.skn',
    fs='fs.skn',
    us_hwd_pron='us_hwd_pron.skn',
    gb_hwd_pron='gb_hwd_pron.skn',
    picture='picture.skn',
    phrases='phrases.skn',
    sfx='sfx.skn',
    thesaurus='thesaurus.skn',
    gram='gram.skn',
    collocations='collocations.skn',
    exa_pron='exa_pron.skn',
    common_errors='common_errors.skn',
    word_sets='word_sets.skn',
    menus='menus.skn',
    #teacher='teacher.skn',
    #pronpractice='pronpractice.skn',
    word_lists='word_lists.skn',
    verb_forms='verb_forms.skn',
    activator='activator.skn',
    activator_section=os.path.join(
        'activator.skn', 'activator_section.skn'),
    activator_concept=os.path.join(
        'activator.skn', 'activator_concept.skn'),
)


def get_archive_names():
    return _ARCHIVE_DIRS.keys()


def is_ldoce5_dir(path):
    for archive_path in _ARCHIVE_DIRS.values():
        target_base = os.path.join(path, archive_path)
        f_base = os.path.join(target_base, 'files.skn')
        d_base = os.path.join(target_base, 'dirs.skn')
        if not os.path.isfile(os.path.join(d_base, 'config.cft')):
            return False
        if not os.path.isfile(os.path.join(d_base, 'NAME.tda')):
            return False
        if not os.path.isfile(os.path.join(d_base, 'dirs.dat')):
            return False
        if not os.path.isfile(os.path.join(f_base, 'config.cft')):
            return False
        if not os.path.isfile(os.path.join(f_base, 'NAME.tda')):
            return False
        if not os.path.isfile(os.path.join(f_base, 'files.dat')):
            return False
        if not os.path.isfile(os.path.join(f_base, 'CONTENT.tda')):
            return False
        if not os.path.isfile(os.path.join(f_base, 'CONTENT.tda.tdz')):
            return False
    return True


def list_files(data_root, archive_name):

    def _parse_cft(path):
        cp = SafeConfigParser()
        with open(path, 'r') as f:
            cp.readfp(f)
        r = {}
        r['offsets'] = {}
        offset = 0
        for (opt, value) in cp.items('DAT'):
            if value in _IDM_TYPE_SIZES:
                name = opt.split(',')[0].strip()
                size = _IDM_TYPE_SIZES[value]
                r['offsets'][name] = slice(offset, offset+size)
                offset += size
        r['rsize'] = offset
        return r

    def build_dirpath(i):
        if i < 0 or i >= len(dirs):
            # what's happening?
            return ('', )
        (name, parent) = dirs[i]
        if parent == 0:
            return (name, )
        return build_dirpath(parent) + (name, )

    def _bytes2int(s):
        r = 0
        for c in reversed(bytearray(s)):
            r = r * 256 + c
        return r

    def _load_dirlist(target_base, t_info):
        dirsbase = os.path.join(target_base, 'dirs.skn')
        d_rsize, d_parent = t_info['d_rsize'], t_info['d_parent']

        # name
        with open(os.path.join(dirsbase, 'NAME.tda'), 'rb') as f:
            namelist = [b.decode('utf-8') for b in f.read().split(b'\0')[:-1]]

        # parent
        parentlist = []
        with open(os.path.join(dirsbase, 'dirs.dat'), 'rb') as f:
            while True:
                record = f.read(d_rsize)
                if len(record) != d_rsize:
                    break
                parentlist.append(_bytes2int(record[d_parent]))

        return list(zip(namelist, parentlist))

    def _load_filelist(target_base, t_info):
        filesbase = os.path.join(target_base, 'files.skn')
        f_rsize = t_info['f_rsize']
        f_offset = t_info['f_offset']
        f_parent = t_info['f_parent']

        # name
        with open(os.path.join(filesbase, 'NAME.tda'), 'rb') as f:
            namelist = [b.decode('utf-8') for b in f.read().split(b'\0')[:-1]]

        # dat
        parentlist = []
        offsetlist = []
        with open(os.path.join(filesbase, 'files.dat'), 'rb') as f:
            while True:
                record = f.read(f_rsize)
                if len(record) != f_rsize:
                    break
                offsetlist.append(_bytes2int(record[f_offset]))
                parentlist.append(_bytes2int(record[f_parent]))

        # size
        sizelist = [offsetlist[i + 1] - offsetlist[i] - 1
                    for i in range(len(offsetlist) - 1)]
        sizelist.append(-1)
        return list(zip(namelist, parentlist, offsetlist, sizelist))

    def _load_catalog(target_base):
        filesbase = os.path.join(target_base, 'files.skn')
        catpath = os.path.join(filesbase, 'CONTENT.tda.tdz')
        origsizes, cmpsizes = [], []

        with open(catpath, 'rb') as f:
            while True:
                catrec = f.read(8)
                if len(catrec) != 8:
                    break
                (origsize, cmpsize, ) = unpack('<LL', catrec)
                origsizes.append(origsize)
                cmpsizes.append(cmpsize)

        origoffsets = [0]
        for i in range(len(origsizes) - 1):
            origoffsets.append(origoffsets[i] + origsizes[i])

        cmpoffsets = [0]
        for i in range(len(cmpsizes) - 1):
            cmpoffsets.append(cmpoffsets[i] + cmpsizes[i])

        return origoffsets, origsizes, cmpoffsets, cmpsizes

    def _make_info(archive_path):
        cf = _parse_cft(os.path.join(archive_path, 'files.skn', 'config.cft'))
        cd = _parse_cft(os.path.join(archive_path, 'dirs.skn', 'config.cft'))
        info = {}
        info['f_offset'] = cf['offsets']['$content']
        info['f_parent'] = cf['offsets']['$a_dirs']
        info['f_rsize'] = cf['rsize']
        info['d_parent'] = cd['offsets']['$parent']
        info['d_rsize'] = cd['rsize']
        return info

    # start
    target_base = os.path.join(data_root, _ARCHIVE_DIRS[archive_name])
    info = _make_info(target_base)
    (origoffsets, origsizes, cmpoffsets, cmpsizes) = _load_catalog(target_base)
    dirs = _load_dirlist(target_base, info)
    ci = 0
    for (name, parent, offset, size) in _load_filelist(target_base, info):
        if ci != len(origoffsets) - 1:
            if offset >= origoffsets[ci + 1]:
                ci += 1
        (cmporig, cmpsize) = cmpoffsets[ci], cmpsizes[ci]
        if size < 0:
            size = origsizes[ci] - (offset - origoffsets[ci]) - 1
        (origorig, origsize) = (offset - origoffsets[ci], size)
        location = (cmporig, cmpsize, origorig, origsize)
        yield (build_dirpath(parent), name, location)


class ArchiveReader(object):
    def __init__(self, data_dir, archive_name):
        self._f = None
        content_path = os.path.join(data_dir, os.path.join(
            _ARCHIVE_DIRS[archive_name], 'files.skn', 'CONTENT.tda'))
        self._f = open(content_path, 'rb')
        self._cache = ''
        self._cache_offset = -1
        self._cache_size = -1

    def read(self, location):
        (cmpoffset, cmpsize, origoffset, origsize) = location
        f = self._f
        f.seek(cmpoffset)
        if (self._cache_offset != cmpoffset) or (self._cache_size != cmpsize):
            self._cache = decompress(f.read(cmpsize))
            self._cache_offset = cmpoffset
            self._cache_size = cmpsize
        return self._cache[origoffset:(origoffset+origsize)]

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._f:
            self._f.close()

