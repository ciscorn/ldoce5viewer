"""A pure-python implementation of cdb"""

from struct import Struct
from mmap import mmap, ACCESS_READ

_struct_2L = Struct(b'<LL')
_read_2L = _struct_2L.unpack
_write_2L = _struct_2L.pack
_read_512L = Struct(b'<512L').unpack

try:
    import __builtin__
    range = __builtin__.xrange
except ImportError:
    pass

import itertools
zip = getattr(itertools, 'izip', zip)

def hashfunc(s):
    h = 5381
    for c in bytearray(s):
        h = h * 33 & 0xffffffff ^ c
    return h


class CDBError(Exception):
    pass


class CDBReader(object):
    __slots__ = ('_mmap', '_maintable')

    def __init__(self, path):
        self._mmap = None
        with open(path, 'rb') as f:
            mm = self._mmap = mmap(f.fileno(), 0, access=ACCESS_READ)
        if len(mm) < 2048:
            raise CDBError('file too small')
        mt = _read_512L(mm.read(2048))
        self._maintable = tuple(zip(mt[0::2], mt[1::2]))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        if self._mmap:
            self._mmap.close()
            self._mmap = None

    def get(self, key, default=None):
        mm = self._mmap
        hashed = hashfunc(key)
        (hashed_high, subidx) = divmod(hashed, 256)
        (pos_subtable, num_entries) = self._maintable[subidx]
        if pos_subtable <= 2048:
            raise CDBError('broken file')

        def iter_subtable():
            ini = hashed_high % num_entries
            pa = pos_subtable + 8 * ini
            pb = pos_subtable + 8 * num_entries
            for p in range(pa, pb, 8):
                yield _read_2L(mm[p:p+8])
            for p in range(pos_subtable, pa, 8):
                yield _read_2L(mm[p:p+8])

        if num_entries:
            for (h, p) in iter_subtable():
                if p == 0:
                    # not exist
                    break
                if h == hashed:
                    pk = p + 8
                    (klen, vlen) = _read_2L(mm[p:pk])
                    pv = pk + klen
                    if key == mm[pk:pv]:
                        return mm[pv:(pv+vlen)]
        return default

    def __getitem__(self, key):
        r = self.get(key)
        if r is None:
            raise KeyError
        return r

    def __contains__(self, key):
        return (self.get(key) is not None)

    def iteritems(self):
        mm = self._mmap
        read = mm.read
        num = sum(n for (p, n) in self._maintable) // 2
        mm.seek(2048)
        for _ in range(num):
            (klen, vlen) = _read_2L(read(8))
            yield (read(klen), read(vlen))


class CDBMaker(object):
    def __init__(self, f):
        self._f = f
        self._f.seek(2048)
        self._total_size = 0
        self._sub_num = [0] * 256
        self._sub = tuple([] for _ in range(256))

    def add(self, k, v):
        write = self._f.write
        pointer = self._f.tell()
        lenk = len(k)
        lenv = len(v)
        write(_write_2L(lenk, lenv))
        write(k)
        write(v)
        self._total_size += 8 + lenk + lenv
        hashed = hashfunc(k)
        s = hashed & 0xFF
        self._sub_num[s] += 2
        self._sub[s].append((hashed, pointer))

    def finalize(self):
        f = self._f
        sub_num = self._sub_num
        sub_pos = []

        # subtable entries
        def write_subbuf(buf, hashed, pointer):
            hashed_high, subidx = divmod(hashed, 256)
            ini = hashed_high % sub_num[subidx]
            for pos in range(ini * 8, sub_num[subidx] * 8, 8):
                h, p = _read_2L(bytes(buf[pos: pos+8]))
                if p == 0:
                    buf[pos:pos+8] = _write_2L(hashed, pointer)
                    return
            for pos in range(0, ini * 8, 8):
                h, p = _read_2L(bytes(buf[pos: pos+8]))
                if p == 0:
                    buf[pos:pos+8] = _write_2L(hashed, pointer)
                    return

        sub_pos = []
        for s in range(256):
            buf = bytearray(self._sub_num[s] * 8)
            for hashed, pos in self._sub[s]:
                write_subbuf(buf, hashed, pos)
            sub_pos.append(f.tell())
            f.write(bytes(buf))

        # header
        f.seek(0)
        for i in range(256):
            f.write(_write_2L(sub_pos[i], sub_num[i]))
