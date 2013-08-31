from __future__ import absolute_import

import zlib
import os.path
import traceback

from .filemap import FilemapReader
from .idmreader import ArchiveReader
from . import transform
from ..utils.cdb import CDBError, CDBReader


class NotFoundError(Exception):
    pass

class FilemapError(Exception):
    pass

class ArchiveError(Exception):
    pass


def load_from_cdb_archive(data_dir, archive_name, name):
    path = os.path.join(data_dir, 'cdb_archives', archive_name + '.cdb')
    with CDBReader(path) as db:
        data = db[name.encode('utf-8')]
        if data[0] == 'c':
            data = zlib.decompress(data[1:])
        else:
            data = data[1:]
        return data


class LDOCE5(object):
    def __init__(self, data_dir, filemap_path):
        self._data_dir = data_dir
        self._filemap_path = filemap_path

    def get_content(self, path):
        try:
            archive, name = path.lstrip('/').split('/', 1)
        except ValueError:
            raise NotFoundError(u'invalid path')

        def load_content(archive_name, name):
            #try:
            #    return load_from_cdb_archive(
            #            self._data_dir, archive_name, name)
            #except IOError:
            #    pass

            try:
                with FilemapReader(self._filemap_path) as fmr:
                    location = fmr.lookup(archive_name, name)
            except (IOError, CDBError):
                raise FilemapError
            except KeyError:
                raise NotFoundError(u'content not found in filemap')
            try:
                with ArchiveReader(self._data_dir, archive_name) as reader:
                    return reader.read(location)
            except IOError:
                raise ArchiveError

        def transform_exc(tf, *data):
            try:
                return tf(*data)
            except:
                exc = traceback.format_exc()
                if isinstance(exc, bytes):
                    exc = traceback.format_exc().decode('utf-8', 'replace')
                s = u"<h2>Error</h2><div>{0}</div>".format(
                        u'<br>'.join(exc.splitlines()))
                return s.encode('utf-8')

        ret_data = None
        mime_type = None

        if archive == 'fs':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_entry, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'collocations':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_collocations, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'examples':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_examples, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'word_families':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_word_families, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'etymologies':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_etymologies, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'activator':
            try:
                cid, sid = name.split('/', 1)
            except ValueError:
                raise NotFoundError('invalid path')
            data_c = load_content('activator_concept', cid)
            data_s = load_content('activator_section', sid)
            ret_data = transform_exc(transform.trans_activator,
                    data_c, data_s, sid)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'phrases':
            data = load_content(archive, name)
            ret_data = transform_exc(transform.trans_phrases, data)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'thesaurus':
            data_set = [load_content('thesaurus', n)
                    for n in name.split('_')]
            ret_data = transform_exc(transform.trans_thesaurus, data_set)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'word_sets':
            data_set = [load_content('word_sets', n)
                    for n in name.split('_')]
            ret_data = transform_exc(transform.trans_word_sets,data_set)
            mime_type = 'text/html;charset=utf-8'

        elif archive == 'picture':
            ret_data = load_content('picture', name)
            mime_type = 'image/jpeg'

        elif archive in ('us_hwd_pron', 'gb_hwd_pron', 'exa_pron', 'sfx'):
            ret_data = load_content(archive, name)
            mime_type = 'audio/mpeg'

        return (ret_data, mime_type)

