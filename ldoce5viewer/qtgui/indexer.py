'''Indexing thread and dialog window'''

from __future__ import absolute_import
from __future__ import unicode_literals

import os
import os.path
import shutil
try:
    import cPickle as pickle
except:
    import pickle
from cgi import escape
from struct import Struct
import traceback

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import lxml.etree as et

from .. import __version__
from .. import fulltext
from .. import incremental
from ..ldoce5 import filemap
from ..ldoce5 import idmreader
from ..ldoce5.extract import get_entry_items
from ..utils.compat import range

from .ui.indexer import Ui_Dialog
from .config import get_config

_struct_I = Struct(b'<I')
_pack_I = _struct_I.pack
_unpack_I = _struct_I.unpack


class AbortIndexing(Exception):
    pass


class IndexerDialog(QDialog):
    def __init__(self, parent, autostart=False):
        QDialog.__init__(self, parent)

        self._thread = None
        self._autostart = autostart

        self._ui = Ui_Dialog()
        self._ui.setupUi(self)

        self._ui.buttonCancel.clicked.connect(self._onCancel)
        self._ui.buttonBrowseSource.clicked.connect(self._onBrowseSource)
        self._ui.lineEditPath.textChanged.connect(self._onSourcePathChanged)
        self._ui.buttonRun.clicked.connect(self._onButtonStartIndexing)
        self._ui.buttonRun.setEnabled(False)

        self._discoverSource()

    def _message(self, s):
        self._ui.plainTextEdit.appendHtml(s)

    def _discoverSource(self):
        path = []
        try:
            import _winreg
            k = _winreg.OpenKey(
                _winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\NSIS_ldoce5")
            try:
                (value, ty) = _winreg.QueryValueEx(k, "Install_Dir")
                if ty == 1:
                    path.append(os.path.join(value, "ldoce5.data"))
            finally:
                _winreg.CloseKey(k)
        except:
            pass

        if 'ProgramFiles' in os.environ:
            path.append(os.path.join(os.environ['ProgramFiles'],
                        'Longman', 'LDOCE5', 'ldoce5.data'))

        if 'ProgramFiles(x86)' in os.environ:
            path.append(os.path.join(os.environ['ProgramFiles(x86)'],
                        'Longman', 'LDOCE5', 'ldoce5.data'))
        for p in path:
            if idmreader.is_ldoce5_dir(p):
                self._ui.lineEditPath.setText(p)
                return

        self._message('Cannot find the "ldoce5.data" folder automatically.')
        self._message('Click the "Browse..." button to '
                      'select the "ldoce5.data" folder.')

    def _onSourcePathChanged(self, text):
        is_valid_dir = idmreader.is_ldoce5_dir(text)
        self._ui.buttonRun.setEnabled(is_valid_dir)
        if is_valid_dir:
            self._ui.plainTextEdit.clear()
            self._message(
                'The "ldoce5.data" folder is found.<br>'
                'Click "Start Indexing" or "Cancel".')
            if self._autostart:
                self._start_indexing()
        else:
            self._message("{0} is not the LDOCE5 archive.".format(text))

    def _onBrowseSource(self):
        dirpath= QFileDialog.getExistingDirectory(
            self, 'Select "ldoce5.data" Folder')
        self._ui.lineEditPath.setText(dirpath)

    def _start_indexing(self):
        config = get_config()
        config.pop('dataDir', None)
        config.pop('versionIndexed', None)
        self._ui.buttonRun.setVisible(False)
        self._ui.lineEditPath.setEnabled(False)
        self._ui.buttonBrowseSource.setVisible(False)
        self.setWindowTitle("Indexing...")

        self._ui.plainTextEdit.clear()
        self._srcdir = self._ui.lineEditPath.text()

        if self._thread:
            self._thread.wait()
            self._thread = None

        self._thread = IndexingThread(self, self._srcdir)
        self._thread.finished.connect(self._onThreadFinished)
        self._thread.message.connect(self._message)
        self._thread.start()

    def _onButtonStartIndexing(self):
        self._start_indexing()

    def _onThreadFinished(self):
        if self._thread:
            self._thread.wait()
            if self._thread.succeeded:
                self._threadSucceeded()
            else:
                self._threadFailed()
            self._thread = None

    def _threadSucceeded(self):
        config = get_config()
        config['dataDir'] = self._srcdir
        config['versionIndexed'] = __version__
        config.save()
        self.setWindowTitle("Done")
        QMessageBox.information(self,
                "Done", "Index successfully created!")
        self.accept()

    def _threadFailed(self):
        self._message("Failed to create index")
        self._ui.buttonRun.setVisible(True)
        self._ui.lineEditPath.setEnabled(True)
        self._ui.buttonBrowseSource.setVisible(True)
        self.setWindowTitle("Create Index")

    def _onCancel(self):
        if self._thread:
            self._thread.abort()
            self._thread.wait()
            self._thread = None
        self.reject()


class AbortIndexing(Exception):
    pass


class IndexingThread(QThread):
    message = pyqtSignal(type(''))

    def __init__(self, parent, srcdir):
        QThread.__init__(self, parent)
        self._srcdir = srcdir
        self._abort = False
        self._succeeded = False

    @property
    def succeeded(self):
        return self._succeeded

    def abort(self):
        self._abort = True

    def _message(self, s):
        self.message.emit(s)

    def _make_index(self):

        def scan_entries(scan_temp):
            # entries
            variations = {}
            self._message('Scanning entry files...')
            files = idmreader.list_files(self._srcdir, 'fs')
            count = 0
            with idmreader.ArchiveReader(self._srcdir, 'fs') as archive_reader:
                for (dirs, name, location) in files:
                    if self._abort:
                        raise AbortIndexing()

                    (items, var) = get_entry_items(
                            archive_reader.read(location))

                    for k in var:
                        v = var[k]
                        if not v:
                            continue
                        if k not in variations:
                            variations[k] = set()
                        variations[k].update(v)

                    for (itemtype, label, path, content,
                            sortkey, asfilter, prio) in items:

                        count += 1
                        if count % 10000 == 0:
                            self._message("{0} items found".format(count))

                        if itemtype == 'hm':
                            words = content.split()
                            for w in words:
                                if '-' in w:
                                    content += (' ' + w.replace('-', ''))

                        scan_temp.append(
                                (itemtype, label, path, content, sortkey,
                                    asfilter, prio))

            self._message("{0} items were found.".format(count))

            # word variation database
            self._message('Making the word variation database...')
            with open(get_config().variations_path, "w+b") as f:
                var_writer = fulltext.VariationsWriter(f)
                for k in variations:
                    v = variations[k]
                    var_writer.add(k, v)

                self._message('Finalizing...')
                var_writer.finalize()
                self._message('Done.')

        def scan_activator(scan_temp):
            self._message('Scanning language-activator files...')

            # phrase to keywords
            act_label_path = os.path.join(self._srcdir,
                    "activator.skn", "alpha_index.skn", "LABEL.tda")
            with open(act_label_path, "rb") as f:
                labels = f.read().split(b"\0")[:-1]

            # activator sections
            sections = {}
            files = idmreader.list_files(self._srcdir, 'activator_section')
            with idmreader.ArchiveReader(
                    self._srcdir, 'activator_section') as cr:
                for (dirs, name, location) in files:
                    if self._abort:
                        raise AbortIndexing()

                    data = cr.read(location)
                    root = et.fromstring(data)
                    sid = root.get('id')
                    sections[sid] = []
                    for exp in root.iterfind("Exponent"):
                        eid = exp.get('id')
                        plain = ''.join(exp.find("EXP").itertext()).strip()
                        sections[sid].append((eid, plain))

            # activator concepts
            files = idmreader.list_files(self._srcdir, 'activator_concept')
            exponents = []
            with idmreader.ArchiveReader(
                    self._srcdir, 'activator_concept') as cr:
                for (dirs, name, location) in files:
                    if self._abort:
                        raise AbortIndexing()

                    root = et.fromstring(cr.read(location))
                    cid = root.get('id')
                    hwd = root.find("HWD").text
                    first_sid = root.find("Section").get('id')
                    for h in hwd.split('/'):
                        scan_temp.append(
                            ('ac', '<a><c>{0}</c></a>'.format(escape(h)),
                            '/activator/{0}/{1}'.format(cid, first_sid),
                            h, h, '', 50))

                    for sno, section in enumerate(root.iterfind("Section")):
                        sid = section.get('id')
                        for (eid, plain) in sections[sid]:
                            exponents.append(
                                    (plain, hwd, cid, sid, eid, sno))

            for (plain, hwd, cid, sid, eid, sno) in exponents:
                if self._abort:
                    raise AbortIndexing()

                keywords = set([plain])
                #if plain in phrase_keys:
                #    keywords.update(phrase_keys[plain])
                for keyword in keywords:
                    scan_temp.append((
                        'ae',
                        '<a><e>{0}</e> (<c>{1}<s>{2}</s></c>)</a>'.format(
                            escape(keyword), escape(hwd), sno+1),
                        '/activator/{0}/{1}#{2}'.format(cid, sid, eid),
                        keyword, keyword, '', 51))

            self._message('Done.')

        def make_incr(scan_temp):
            self._message('Building the incremental search index...')
            incr_maker = incremental.Maker(get_config().incremental_path,
                    get_config().incremental_path + get_config().tmp_suffix)

            i = 0
            for (itemtype, label, path, content,
                    sortkey, asfilter, prio) in scan_temp.iter_items():
                if self._abort:
                    raise AbortIndexing()
                ty = itemtype[0]
                if ty == 'p' or ty == 'h' or ty == 'a':
                    i += 1
                    if i % 10000 == 0:
                        self._message('{0} items added'.format(i))
                    incr_maker.add_item(content, itemtype, label, path, prio)

            self._message('{0} items were added.'.format(i))
            self._message('Finalizing...')
            incr_maker.finalize()

            self._message('Done.')

        def make_full_hp(scan_temp):
            self._message('Building the full text search index '
                    'for headwords and phrases...')
            fulltext_hwdphr_maker = fulltext.Maker(
                    get_config().fulltext_hwdphr_path)

            i = 0
            for (itemtype, label, path, content,
                    sortkey, asfilter, prio) in scan_temp.iter_items():
                if self._abort:
                    raise AbortIndexing()
                ty = itemtype[0]
                if ty == 'p' or ty == 'h' or ty == 'a':
                    i += 1
                    if i % 10000 == 0:
                        self._message('{0} items added'.format(i))
                    fulltext_hwdphr_maker.add_item(itemtype, content, asfilter,
                            label, path, prio, sortkey)

            self._message('{0} items were added.'.format(i))
            self._message('Finalizing...')
            self._message('Please wait a while...')
            fulltext_hwdphr_maker.commit()
            fulltext_hwdphr_maker.close()

            self._message('Done.')

        def make_full_de(scan_temp):
            self._message('Building the full text search index '
                    'for examples and definitions...')
            fulltext_defexa_maker = fulltext.Maker(
                    get_config().fulltext_defexa_path)

            i = 0
            for (itemtype, label, path, content,
                    sortkey, asfilter, prio) in scan_temp.iter_items():
                if self._abort:
                    raise AbortIndexing()
                ty = itemtype[0]
                if ty == 'd' or ty == 'e':
                    i += 1
                    if i % 10000 == 0:
                        self._message('{0} items added'.format(i))
                    fulltext_defexa_maker.add_item(itemtype, content, asfilter,
                            label, path, prio, sortkey)

            self._message('{0} items were added.'.format(i))
            self._message('Finalizing...')
            self._message('Please wait a while...')
            fulltext_defexa_maker.commit()
            fulltext_defexa_maker.close()
            self._message('Done.')

        scan_temp = ScanTempFile(get_config().scan_tmp_path)
        try:
            scan_entries(scan_temp)
            scan_activator(scan_temp)
            make_incr(scan_temp)
            make_full_hp(scan_temp)
            make_full_de(scan_temp)
        finally:
            scan_temp.remove()

    def _make_filemap(self):
        self._message("Building the file-location lookup table...")
        with open(get_config().filemap_path, "w+b") as f:
            maker = filemap.FilemapMaker(f)
            for archive_name in idmreader.get_archive_names():
                self._message("Analyzing '{0}'...".format(archive_name))
                file_iter = filemap.list_files(self._srcdir, archive_name)
                for (name, location) in file_iter:
                    if self._abort:
                        raise AbortIndexing()

                    maker.add(archive_name, name, location)

            self._message("Finalizing...")
            maker.finalize()

    def _remove_all(self):
        def rm(path):
            if os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)

        config = get_config()
        rm(config.filemap_path)
        rm(config.incremental_path)
        rm(config.variations_path)
        rm(config.fulltext_defexa_path)
        rm(config.fulltext_hwdphr_path)

    def run(self):
        err = False
        try:
            self._remove_all()
            self._make_filemap()
            self._make_index()
            self._message('Completed!')
        except AbortIndexing:
            self._message("Aborted!")
            err = True
        except Exception:
            self._message(
                "<div style='color: red'>"
                "Error occurred<br>{0}</div>".format(
                    '<br>'.join(traceback.format_exc().splitlines())))
            err = True

        if err:
            try:
                self._message("Removing files...")
                self._remove_all()
            except:
                pass
        else:
            self._succeeded = True


class ScanTempFile(object):
    def __init__(self, path):
        self._path = path
        self._n = 0
        self._f = open(path, "w+b")

    def append(self, item):
        data = pickle.dumps(item)
        f = self._f
        f.write(_pack_I(len(data)))
        f.write(data)
        self._n += 1

    def iter_items(self):
        f = self._f
        f.seek(0)
        for _ in range(self._n):
            (lendata,) = _unpack_I(f.read(4))
            data = f.read(lendata)
            yield pickle.loads(data)

    def remove(self):
        self._f.close()
        try:
            os.remove(self._path)
        except EnvironmentError:
            pass

