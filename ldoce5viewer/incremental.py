"""Incremental searcher for headwords and phrases"""

import mmap
import os
from operator import itemgetter
from struct import Struct

from .utils.text import dec_utf8, enc_utf8, normalize_index_key

_MAGIC = 0x28061691
_DB_VERSION = 1


_struct_I = Struct(b"<I")
_pack_I = _struct_I.pack
_unpack_I = _struct_I.unpack
del _struct_I
_struct_HBHHB = Struct(b"<HBHHB")
_pack_HBHHB = _struct_HBHHB.pack
_unpack_HBHHB = _struct_HBHHB.unpack
del _struct_HBHHB
_unpack_H = Struct(b"<H").unpack


class IndexError(Exception):
    pass


class Searcher(object):
    def __init__(self, index_path):
        self._mm = None
        try:
            with open(index_path, "rb") as f:
                self._mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:
            raise IndexError("broken")

        read = self._mm.read
        file_size = len(self._mm)

        if file_size < 4 * 4:
            raise IndexError("too small")
        if _MAGIC != _unpack_I(read(4))[0]:
            raise IndexError("broken")
        if _DB_VERSION != _unpack_I(read(4))[0]:
            raise IndexError("cannot use this version of index")

        (self._num,) = _unpack_I(read(4))
        (self._first,) = _unpack_I(read(4))
        if self._num == 0 or self._first == 0:
            raise IndexError("does not contain any data")
        if file_size != self._first + self._num * 4:
            raise IndexError("broken")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        if self._mm:
            self._mm.close()
            self._mm = None

    def search(self, key, limit):
        key = normalize_index_key(key)
        if not key:
            return []

        mm = self._mm
        num = self._num
        first = self._first

        def bisect_start(key):
            (a, b) = (0, num)
            while a != b:
                c = (a + b) // 2
                p = first + 4 * c
                (p,) = _unpack_I(mm[p : p + 4])
                (lenp,) = _unpack_H(mm[p : p + 2])
                p += 8
                plain = dec_utf8(mm[p : p + lenp])
                if key > plain:
                    a = c + 1
                else:
                    b = c
            return a

        def bisect_end(key, start):
            (a, b) = (start, num)
            while a != b:
                c = (a + b) // 2
                p = first + 4 * c
                (p,) = _unpack_I(mm[p : p + 4])
                (lenp,) = _unpack_H(mm[p : p + 2])
                p += 8
                plain = dec_utf8(mm[p : p + lenp])
                if key < plain and not plain.startswith(key):
                    b = c
                else:
                    a = c + 1
            return a

        start = bisect_start(key)
        end = bisect_end(key, start)

        if start == num:
            return []

        (seek, read) = (mm.seek, mm.read)
        ret = [None] * min(limit, end - start)
        p = first + 4 * start
        seek(_unpack_I(mm[p : p + 4])[0])
        for i in range(len(ret)):
            (lenplain, lentypecode, lenlabel, lenpath, prio) = _unpack_HBHHB(read(8))
            data = read(lenplain + lentypecode + lenlabel + lenpath)
            plain = dec_utf8(data[:lenplain])
            x1 = lenplain + lentypecode
            x2 = x1 + lenlabel
            # typecode = data[lenplain:x1]
            label = dec_utf8(data[x1:x2])
            path = dec_utf8(data[-lenpath:])
            ret[i] = (label, path, plain, prio, None)

        return ret


class Maker(object):
    def __init__(self, path, tmp_path):
        self._items = []
        self._path = path
        self._tmp_path = tmp_path
        self._tmpf = open(tmp_path, "wb")

    def add_item(self, plain, typecode, label, path, prio):
        plain_n = normalize_index_key(plain)
        plain_e = enc_utf8(plain_n)
        typecode_e = enc_utf8(typecode)
        label_e = enc_utf8(label)
        path_e = path.encode("ascii")
        data = b"".join(
            (
                _pack_HBHHB(
                    len(plain_e), len(typecode_e), len(label_e), len(path_e), prio
                ),
                plain_e,
                typecode_e,
                label_e,
                path_e,
            )
        )
        tmpf = self._tmpf
        pos = tmpf.tell()
        tmpf.write(data)
        self._items.append((pos, plain_n, prio))

    def abort(self):
        if self._tmpf:
            self._tmpf.close()
            self._tmpf = None
            os.remove(self._tmp_path)

    def finalize(self):
        tmpf = self._tmpf
        num = len(self._items)
        first = tmpf.tell()

        # Sort by (plain_n, prio)
        self._items.sort(key=itemgetter(1, 2))

        for item in self._items:
            tmpf.write(_pack_I(item[0]))
        del self._items

        self._tmpf.close()
        self._tmpf = None
        try:
            self._generate(num, first)
        except:
            raise
        finally:
            os.remove(self._tmp_path)

    def _generate(self, num, first):
        try:
            with open(self._tmp_path, "rb") as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:
            raise IndexError("index is broken")

        if len(mm) != first + num * 4:
            raise IndexError("index is broken")

        dstf = open(self._path, "wb")

        write = dstf.write
        write(_pack_I(_MAGIC))
        write(_pack_I(_DB_VERSION))
        write(_pack_I(num))
        write(_pack_I(first + 4 * 4))

        new_xlist = []
        p = first
        newx = 4 * 4
        for i in range(num):
            new_xlist.append(newx)
            x = _unpack_I(mm[p : p + 4])[0]
            sizes = mm[x : (x + 8)]
            (lenplain, lentypecode, lenlabel, lenpath, prio) = _unpack_HBHHB(sizes)
            datasize = lenplain + lentypecode + lenlabel + lenpath
            data = mm[x : (x + 8 + datasize)]
            write(data)
            p += 4
            newx += 8 + datasize

        for x in new_xlist:
            write(_pack_I(x))

        dstf.close()
        mm.close()
