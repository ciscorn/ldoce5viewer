'''Global configurations'''

from __future__ import absolute_import, unicode_literals, print_function

import sys
import os
import os.path
import tempfile
import shutil
try:
    import cPickle as pickle
except ImportError:
    import pickle

from PyQt5.QtCore import QReadWriteLock


__config = None


def get_config():
    global __config
    if not __config:
        __config = __Config()
    return __config


class __Config(object):
    def __init__(self, debug=False):
        self.debug = debug
        self._dict = dict()
        self._prepare_dir()
        self._remove_tmps()
        self._lock = QReadWriteLock()

    def __getitem__(self, key):
        self._lock.lockForRead()
        r = self._dict[key]
        self._lock.unlock()
        return r

    def __setitem__(self, key, value):
        self._lock.lockForWrite()
        self._dict[key] = value
        self._lock.unlock()

    def get(self, key, default=None):
        self._lock.lockForRead()
        r = self._dict.get(key, default)
        self._lock.unlock()
        return r

    def pop(self, key, default=None):
        self._lock.lockForWrite()
        r = self._dict.pop(key, default)
        self._lock.unlock()
        return r

    def __contains__(self, key):
        self._lock.lockForRead()
        r = self._dict.__contains__(key)
        self._lock.unlock()
        return r

    def __str__(self):
        self._lock.lockForRead()
        s = ''.join([
            'Config(',
            ', '.join("{0}: {1}".format(k, v) for (k, v) in self._dict),
            ')'])
        self._lock.unlock()
        return s

    @property
    def _config_dir(self):
        # Windows
        if sys.platform.startswith('win'):
            if 'LOCALAPPDATA' in os.environ:
                return os.path.join(
                    os.environ['LOCALAPPDATA'], 'LDOCE5Viewer')
            else:
                return os.path.join(
                    os.environ['APPDATA'], 'LDOCE5Viewer')
        # Mac OS X
        elif sys.platform.startswith('darwin'):
            return os.path.expanduser(
                '~/Library/Application Support/LDOCE5Viewer')
        # Linux
        else:
            base = os.path.join(os.path.expanduser('~'), '.config')
            # XDG
            try:
                import xdg.BaseDirectory
                base = xdg.BaseDirectory.xdg_config_home
            except ImportError:
                if 'XDG_CONFIG_HOME' in os.environ:
                    base = os.environ['XDG_CONFIG_HOME']
            return os.path.join(base, 'ldoce5viewer')

    @property
    def _data_dir(self):
        # Windows
        if sys.platform.startswith('win'):
            return self._config_dir
        # Mac OS X
        elif sys.platform.startswith('darwin'):
            return self._config_dir
        # Linux
        else:
            base = os.path.join(os.path.expanduser('~'), '.local/share/')
            # XDG
            try:
                import xdg.BaseDirectory
                base = xdg.BaseDirectory.xdg_data_home
            except ImportError:
                if 'XDG_DATA_HOME' in os.environ:
                    base = os.environ['XDG_DATA_HOME']
            return os.path.join(base, 'ldoce5viewer')

    @property
    def app_name(self):
        return 'LDOCE5 Viewer'

    @property
    def _config_path(self):
        return os.path.join(self._config_dir, 'config.pickle')

    @property
    def filemap_path(self):
        return os.path.join(self._data_dir, 'filemap.cdb')

    @property
    def variations_path(self):
        return os.path.join(self._data_dir, 'variations.cdb')

    @property
    def incremental_path(self):
        return os.path.join(self._data_dir, 'incremental.db')

    @property
    def fulltext_hwdphr_path(self):
        return os.path.join(self._data_dir, 'fulltext_hp')

    @property
    def fulltext_defexa_path(self):
        return os.path.join(self._data_dir, 'fulltext_de')

    @property
    def scan_tmp_path(self):
        return os.path.join(self._data_dir, 'scan' + self.tmp_suffix)

    @property
    def tmp_suffix(self):
        return '.tmp'

    def _remove_tmps(self):
        for name in os.listdir(self._config_dir) + os.listdir(self._data_dir):
            if name.endswith(self.tmp_suffix):
                path = os.path.join(self._config_dir, name)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except OSError:
                    pass

    def _prepare_dir(self):
        if not os.path.exists(self._config_dir):
            os.makedirs(self._config_dir)
        if not os.path.exists(self._data_dir):
            os.makedirs(self._data_dir)

    def load(self):
        self._lock.lockForWrite()
        try:
            with open(self._config_path, 'rb') as f:
                self._dict.clear()
                try:
                    data = pickle.load(f)
                except:
                    pass
                else:
                    self._dict.update(data)
        except IOError:
            self._dict.clear()
        self._lock.unlock()

    def save(self):
        self._lock.lockForRead()

        if sys.platform == 'win32':
            with open(self._config_path, 'wb') as f:
                pickle.dump(self._dict, f)
        else:
            f = tempfile.NamedTemporaryFile(
                dir=self._config_dir, delete=False, suffix=self.tmp_suffix)
            pickle.dump(self._dict, f, protocol=0)
            f.close()
            os.rename(f.name, self._config_path)

        self._lock.unlock()
