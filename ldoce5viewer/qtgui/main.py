'''Main window'''

from __future__ import absolute_import
from __future__ import unicode_literals

import sys
from operator import itemgetter
from functools import partial
from difflib import SequenceMatcher
try:
    from itertools import imap as map
except ImportError:
    pass
import webbrowser

try:
    import objc
    import Cocoa
    import Foundation
except ImportError:
    objc = None

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtNetwork import *
from PyQt5.QtWebKit import *
from PyQt5.QtWebKitWidgets import *
from PyQt5.QtWidgets import *
from PyQt5.QtPrintSupport import *

from .. import fulltext
from .. import incremental
from ..ldoce5.idmreader import is_ldoce5_dir
from ..utils.compat import range
from ..utils.text import (MATCH_OPEN_TAG, MATCH_CLOSE_TAG, ellipsis,
                          normalize_index_key)

from . import indexer
from .advanced import AdvancedSearchDialog
from .config import get_config
from .access import MyNetworkAccessManager, _load_static_data
from .async_ import AsyncFTSearcher
from .utils.soundplayer import create_soundplayer
from .indexer import IndexerDialog
from .ui.custom import ToolButton, LineEdit
from .ui.main import Ui_MainWindow


# Config
_INDEX_SUPPORTED = "2013.02.25"
_FTS_HWDPHR_LIMIT = 10000
_INCREMENTAL_LIMIT = 500
_MAX_DELAY_UPDATE_INDEX = 100
_INTERVAL_AUTO_PRON = 50
_LOCAL_SCHEMES = frozenset(('dict', 'static', 'search', 'audio'))
_HELP_PAGE_URL = "http://hakidame.net/ldoce5viewer/manual/"


# Identifiers for lazy-loaded objects
_LAZY_INCREMENTAL = 'incremental'
_LAZY_FTS_HWDPHR = 'fts_hwdphr'
_LAZY_FTS_DEFEXA = 'fts_defexa'
_LAZY_FTS_HWDPHR_ASYNC = 'fts_hwdphr_async'
_LAZY_SOUNDPLAYER = 'soundplayer'
_LAZY_ADVSEARCH_WINDOW = 'advsearch_window'
_LAZY_PRINTER = 'printer'


_IS_OSX = sys.platform.startswith('darwin')


def _incr_delay_func(count):
    x = max(0.3, min(1, float(count) / _INCREMENTAL_LIMIT))
    return int(_MAX_DELAY_UPDATE_INDEX * x)


class MainWindow(QMainWindow):

    #------------
    # MainWindow
    #------------

    def __init__(self):
        super(MainWindow, self).__init__()

        self._okToClose = False
        #systray = QSystemTrayIcon(self)
        #systray.setIcon(QIcon(":/icons/icon.png"))
        #systray.show()
        #def systray_activated(reason):
        #    self.setVisible(self.isVisible() ^ True)
        #systray.activated.connect(systray_activated)

        # results
        self._incr_results = None
        self._fts_results = None
        self._found_items = None

        # status
        self._selection_pending = False
        self._loading_pending = False
        self._auto_fts_phrase = None

        # Lazy-loaded objects
        self._lazy = {}

        # Setup
        self._setup_ui()
        self._restore_from_config()

        # Timers
        def _makeSingleShotTimer(slot):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(slot)
            return timer

        self._timerUpdateIndex = \
                _makeSingleShotTimer(self._updateIndex)
        self._timerAutoFTS = \
                _makeSingleShotTimer(self._onTimerAutoFullSearchTimeout)
        self._timerAutoPron = \
                _makeSingleShotTimer(self._onTimerAutoPronTimeout)
        self._timerSpellCorrection = \
                _makeSingleShotTimer(self._onTimerSpellCorrection)
        self._timerSearchingLabel = \
                _makeSingleShotTimer(self._onTimerSearchingLabel)

        # Clipboard
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(
                partial(self._onClipboardChanged, mode=QClipboard.Clipboard))
        clipboard.selectionChanged.connect(
            partial(self._onClipboardChanged, mode=QClipboard.Selection))

        # Stylesheet for the item list pane
        try:
            self._ui.listWidgetIndex.setStyleSheet(
                    _load_static_data('styles/list.css')\
                            .decode('utf-8', 'ignore'))
        except EnvironmentError:
            pass

        # Check index
        QTimer.singleShot(0, self._check_index)

        # Show
        self.show()

        # Click on the dock icon (OS X)
        if objc:
            def applicationShouldHandleReopen_hasVisibleWindows_(s, a, f):
                self.show()

            objc.classAddMethods(
                Cocoa.NSApplication.sharedApplication().delegate().class__(),
                [applicationShouldHandleReopen_hasVisibleWindows_])


    def close(self):
        self._okToClose = True
        super(MainWindow, self).close()


    def closeEvent(self, event):
        if not objc:
            self._okToClose = True

        lazy = self._lazy
        if self._okToClose:
            if _LAZY_ADVSEARCH_WINDOW in lazy:
                lazy[_LAZY_ADVSEARCH_WINDOW].close()
            self._save_to_configfile()
            self._unload_searchers()
            if _LAZY_SOUNDPLAYER in lazy:
                lazy[_LAZY_SOUNDPLAYER].close()
            super(MainWindow, self).closeEvent(event)
        else:
            self.hide()
            event.ignore()


    def resizeEvent(self, event):
        ui = self._ui
        sp = self._ui.splitter
        width = event.size().width()
        if width < 350:
            sp.setOrientation(Qt.Vertical)
            ui.actionSearchExamples.setText('E')
            ui.actionSearchDefinitions.setText('D')
            ui.actionAdvancedSearch.setText('A')
        elif width < 550:
            sp.setOrientation(Qt.Vertical)
            ui.actionSearchExamples.setText('Exa')
            ui.actionSearchDefinitions.setText('Def')
            ui.actionAdvancedSearch.setText('Adv')
        elif width < 900:
            sp.setOrientation(Qt.Horizontal)
            ui.actionSearchExamples.setText('Exa')
            ui.actionSearchDefinitions.setText('Def')
            ui.actionAdvancedSearch.setText('Advanced')
        else:
            sp.setOrientation(Qt.Horizontal)
            ui.actionSearchExamples.setText('Examples')
            ui.actionSearchDefinitions.setText('Definitions')
            ui.actionAdvancedSearch.setText('Advanced')


    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        ctrl = Qt.MetaModifier if _IS_OSX else Qt.ControlModifier
        le = self._ui.lineEditSearch

        if key == Qt.Key_Down or \
                (key == Qt.Key_J and modifiers == ctrl) or \
                (key == Qt.Key_Return and modifiers == Qt.NoModifier):
            self.selectItemRelative(1)
        elif key == Qt.Key_Up or \
                (key == Qt.Key_K and modifiers == ctrl) or \
                (key == Qt.Key_Return and modifiers == Qt.ShiftModifier):
            self.selectItemRelative(-1)
        elif key == Qt.Key_Backspace:
            le.setFocus()
            le.setText(self._ui.lineEditSearch.text()[:-1])
        elif key in (Qt.Key_Space, Qt.Key_PageDown, Qt.Key_PageUp,
                Qt.Key_Home, Qt.Key_End):
            self._ui.webView.setFocus()
            self._ui.webView.keyPressEvent(event)
        elif event.text().isalnum():
            le.setFocus()
            le.setText(event.text())
        else:
            super(MainWindow, self).keyPressEvent(event)


    def keyReleaseEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        mouse_buttons = QApplication.mouseButtons()

        ctrl = Qt.MetaModifier if _IS_OSX else Qt.ControlModifier

        if (not event.isAutoRepeat()) and mouse_buttons == Qt.NoButton:
            if key == Qt.Key_Down or \
                    (key == Qt.Key_J and modifiers == ctrl) or \
                    (key == Qt.Key_Return and modifiers == Qt.NoModifier):
                self._loadItem()
            elif key == Qt.Key_Up or \
                 (key == Qt.Key_K and modifiers == ctrl) or \
                 (key == Qt.Key_Return and modifiers == Qt.ShiftModifier):
                self._loadItem()


    def _updateTitle(self, title):
        title = title.strip()
        if title:
            self.setWindowTitle('{title} - {appname}'.format(
                title=title,
                appname=QApplication.applicationName()))
        else:
            self.setWindowTitle(QApplication.applicationName())


    def _onFocusLineEdit(self):
        self._ui.lineEditSearch.selectAll()
        self._ui.lineEditSearch.setFocus()


    #---------
    # Index
    #---------

    def _updateIndex(self):
        """Update the item list"""

        text_getter = itemgetter(0)
        path_getter = itemgetter(1)

        def _replace_htmltags(s):
            def opentag(m):
                return ''.join(('<span class="', m.group(1), '">'))
            s = MATCH_CLOSE_TAG.sub('</span>', s)
            s = MATCH_OPEN_TAG.sub(opentag, s)
            return ''.join(('<body>', s, '</body>'))

        lw = self._ui.listWidgetIndex

        incr_res = self._incr_results
        full_res = self._fts_results

        query = self._ui.lineEditSearch.text().strip()
        if incr_res is not None and full_res is not None\
                and len(incr_res) == 0 and len(full_res) == 0\
                and len(query.split()) == 1:
            self._timerSpellCorrection.start(200)

        # Escape the previous selection
        row_prev = lw.currentRow()
        selected_prev = None
        if row_prev != -1:
            selected_prev = self._found_items[row_prev]

        # Update Index
        if incr_res and full_res:
            closed = set(map(path_getter, incr_res))
            self._found_items = incr_res + tuple(item
                    for item in full_res if path_getter(item) not in closed)
        elif incr_res:
            self._found_items = tuple(incr_res)
        elif full_res:
            self._found_items = tuple(full_res)
        else:
            self._found_items = tuple()

        del incr_res
        del full_res

        # Create a new list
        items = tuple(_replace_htmltags(text_getter(item))
                for item in self._found_items)
        lw.clear()
        lw.addItems(items)

        # Restore the previous selection
        if selected_prev:
            comparer = itemgetter(2, 3, 1) # (sortkey, prio, path)
            current = comparer(selected_prev)
            for row in range(len(self._found_items)):
                if comparer(self._found_items[row]) == current:
                    lw.setCurrentRow(row)
                    break

        url = self._ui.webView.url().toString()
        sel_row = -1
        for (row, path) in enumerate(map(path_getter, self._found_items)):
            if 'dict:' + path == url:
                sel_row = row
                break

        if sel_row >= 0:
            lw.setCurrentRow(sel_row)
            lw.scrollToItem(lw.item(sel_row), QAbstractItemView.EnsureVisible)
        else:
            lw.scrollToTop()

        if self._selection_pending:
            self._selection_pending = False
            self.selectItemRelative()

        if self._loading_pending:
            self._loading_pending = False
            self._loadItem()


    def selectItemRelative(self, rel=0):
        if not self._found_items:
            self._selection_pending = True
            return

        if not self._found_items:
            return

        ui = self._ui
        lw = ui.listWidgetIndex
        row_prev = lw.currentRow()
        sortkey_getter = itemgetter(2)

        if row_prev == -1 or ui.lineEditSearch.hasFocus():
            # Find the prefix/exact match
            text = normalize_index_key(ui.lineEditSearch.text()).lower()
            sortkey_iter = map(sortkey_getter, self._found_items)
            for (row, sortkey) in enumerate(sortkey_iter):
                if sortkey.lower().startswith(text):
                    lw.setFocus()
                    lw.setCurrentRow(row)
                    return

            # find the most similar item
            row = -1
            sm = SequenceMatcher(a=text)
            max_ratio = 0
            sortkeys = map(sortkey_getter, self._found_items)
            for (r, sortkey) in enumerate(sortkeys):
                sm.set_seq2(sortkey)
                ratio = sm.quick_ratio()
                if ratio > max_ratio:
                    max_ratio = ratio
                    row = r
            lw.setFocus()
            lw.setCurrentRow(row)

        else:
            row = max(0, min(len(self._found_items) - 1, row_prev + rel))
            if row != row_prev:
                lw.setFocus()
                lw.setCurrentRow(row)


    def _loadItem(self, row=None):
        if not self._found_items:
            self._loading_pending = True
            return

        if row is None:
            row = self._ui.listWidgetIndex.currentRow()

        if 0 <= row < len(self._found_items):
            path = self._found_items[row][1]
            url = QUrl('dict://' + path)
            if url != self._ui.webView.url():
                self._ui.webView.load(url)


    def _onItemSelectionChanged(self):
        selitems = self._ui.listWidgetIndex.selectedItems()
        if selitems and QApplication.mouseButtons() != Qt.NoButton:
            self._loadItem(self._ui.listWidgetIndex.row(selitems[0]))


    #---------
    # Search
    #---------

    def _instantSearch(self, pending=False, delay=True):
        query = self._ui.lineEditSearch.text()
        self._selection_pending = pending
        self._loading_pending = pending

        self._timerSearchingLabel.stop()
        self._ui.labelSearching.hide()

        if self._fts_hwdphr_async:
            self._fts_hwdphr_async.cancel()

        self._timerUpdateIndex.stop()
        self._timerAutoFTS.stop()
        self._timerSpellCorrection.stop()
        self._incr_results = None
        self._fts_results = None

        if query:
            contains_wild = any(c in query for c in '*?')

            if not contains_wild:
                results = self._incremental_search(query)
            else:
                results = []
            if results is not None:
                self._incr_results = tuple(results)
                self._auto_fts_phrase = query
                self._timerAutoFTS.start(0)
                self._timerUpdateIndex.start(
                        _incr_delay_func(len(results)) if delay else 0)
            else:
                self._ui.webView.setHtml("""<p>The incremental search index"""
                        """ has not been created yet or broken.</p>""")
                self._timerUpdateIndex.start(0)
        else:
            self._timerUpdateIndex.start(0)


    def _onTimerAutoFullSearchTimeout(self):
        query = self._auto_fts_phrase
        if self._fts_hwdphr_async:
            if any(c in query for c in "?*"):
                itemtypes = ('hm', )
            else:
                itemtypes = ()
            self._timerSearchingLabel.start(200)
            self._fts_hwdphr_async.update_query(
                    query_str1=query,
                    itemtypes=itemtypes,
                    limit=_FTS_HWDPHR_LIMIT+1,
                    merge=True)


    def _onTimerSpellCorrection(self):
        query = self._ui.lineEditSearch.text()
        if len(query.split()) == 1:
            words = self._fts_hwdphr.correct(query)
            cmpl = QCompleter(words, self)
            cmpl.setModelSorting(QCompleter.UnsortedModel)
            cmpl.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
            self._ui.lineEditSearch.setCompleter(cmpl)
            cmpl.complete()
            def cmpl_activated(s):
                self._instantSearch()
            cmpl.activated.connect(cmpl_activated)

    def _incremental_search(self, key):
        if not self._incremental:
            return None
        else:
            try:
                return self._incremental.search(key, limit=_INCREMENTAL_LIMIT)
            except (EnvironmentError, incremental.IndexError):
                return None


    def _onAsyncFTSearchFinished(self):
        self._timerSearchingLabel.stop()
        self._ui.labelSearching.hide()
        r = self._fts_hwdphr_async.take_result()
        if r is None:
            return
        (merge, result) = r

        if not merge:
            self._incr_results = None
        self._fts_results = tuple(result)
        self._timerUpdateIndex.start(0)


    def _onAsyncFTSearchError(self):
        self._timerSearchingLabel.stop()
        self._ui.labelSearching.hide()
        self._ui.webView.setHtml(
                """<p>The full-text search index """
                """has not been created yet or broken.</p>""")


    def _onTimerSearchingLabel(self):
        self._ui.labelSearching.show()


    #------------
    # Search Box
    #------------

    def _onTextChanged(self, text):
        text = text.strip()
        not_empty = bool(text)
        self._ui.actionSearchExamples.setEnabled(not_empty)
        self._ui.actionSearchDefinitions.setEnabled(not_empty)

    def _onTextEdited(self, text):
        self._ui.lineEditSearch.setCompleter(None)
        self._instantSearch()

    #----------
    # WebView
    #----------

    def _playbackAudio(self, path):
        self._getAudioData(path, lambda data: self._soundplayer.play(data))

    def _getAudioData(self,  path,  callback):
        (archive, name) = path.lstrip('/').split('/', 1)
        if archive in ('us_hwd_pron', 'gb_hwd_pron', 'exa_pron', 'sfx', 'sound'):
            def finished():
                if reply.error() == QNetworkReply.NoError:
                    callback(reply.readAll())

            url = QUrl('dict:///{0}/{1}'.format(archive, name))
            reply = self._networkAccessManager.get(QNetworkRequest(url))
            reply.finished.connect(finished)

    def downloadSelectedAudio(self):
        path = self._ui.webView.audioUrlToDownload.path()
        def showSaveDialog(data):
            filename = QFileDialog.getSaveFileName(self,  u'Save mp3', \
                '',  u'MP3 Files (*.mp3)')
            if type(filename) is tuple:
                filename = filename[0]

            if filename != '':
                file = open(filename, "wb")
                file.write(data)
                file.close()
        self._getAudioData(path, showSaveDialog)

    def _onWebViewLinkClicked(self, url):
        scheme = url.scheme()
        if scheme == 'audio':
            self._playbackAudio(url.path())
        elif scheme == 'lookup':
            urlQuery = QUrlQuery(url)
            query = dict(urlQuery.queryItems())
            if 'q' in query:
                q = query['q'].replace('+', ' ')
                self._ui.lineEditSearch.setText(q)
                self._instantSearch(pending=True, delay=False)
        elif scheme in _LOCAL_SCHEMES:
            self._ui.webView.load(url)
        else:
            # not a local scheme
            webbrowser.open(str(url.toEncoded()))


    def _onWebViewWheelWithCtrl(self, delta):
        self.setZoom(delta / 120.0, relative=True)


    def setZoom(self, val, relative=False):
        config = get_config()
        zoom_power = val
        if relative:
            zoom_power += config.get('zoomPower', 0)
        config['zoomPower'] = max(-10, min(20, zoom_power))
        self._ui.webView.setZoomFactor(1.05 ** config['zoomPower'])


    def _onLoadFinished(self, succeeded):
        if succeeded:
            not_empty = bool(self._ui.lineEditSearch.text().strip())
            self._ui.actionSearchExamples.setEnabled(not_empty)
            self._ui.actionSearchDefinitions.setEnabled(not_empty)
            self._updateTitle(self._ui.webView.title())


    def _onUrlChanged(self, url):
        history = self._ui.webView.history()
        if history.currentItemIndex() == 1 and \
                history.itemAt(0).url() == QUrl('about:blank'):
            history.clear()

        # Update history menu
        def update_navmenu(menu, items, curidx, back):
            def make_goto(idx):
                def f():
                    history = self._ui.webView.history()
                    if 0 <= idx < history.count():
                        history.goToItem(history.itemAt(idx))
                return f

            items = [(idx, item) for (idx, item) in enumerate(items)]
            if back:
                items = items[max(0, curidx-20):curidx]
                items.reverse()
            else:
                items = items[curidx+1:curidx+1+20]
            urlset = set()
            menu.clear()
            for idx, hitem in items:
                title = hitem.title()
                if (not title) or hitem.url() in urlset:
                    continue
                urlset.add(hitem.url())
                title = ellipsis(title, 20)
                try:
                    menu.addAction(title, make_goto(idx))
                except:
                    pass
            menu.setEnabled(bool(menu.actions()))

        items = history.items()
        curidx = history.currentItemIndex()
        update_navmenu(self._ui.menuBackHistory, items, curidx, True)
        update_navmenu(self._ui.menuForwardHistory, items, curidx, False)

        # auto pronunciation playback
        if not history.canGoForward():
            self._autoPronPlayback()

        # restore search phrase
        hist_item = history.currentItem()
        curr_query = self._ui.lineEditSearch.text()
        hist_query = hist_item.userData()
        if hist_query:
            if hist_query != curr_query:
                self._ui.lineEditSearch.setText(hist_query)
                self._instantSearch()
            else:
                self._timerUpdateIndex.start(0)
        else:
            history.currentItem().setUserData(curr_query)


    #-----------------
    # Advanced Search
    #-----------------

    def fullSearch(self, phrase, filters, mode=None, only_web=False):
        self._selection_pending = False
        self._loading_pending = False
        self._ui.lineEditSearch.setText(phrase or "")

        if (not only_web) and self._fts_hwdphr_async:
            self._incr_results = tuple()
            self._fts_results = None
            self._timerSearchingLabel.start(200)
            self._ui.labelSearching.show()
            self._fts_hwdphr_async.update_query(
                    query_str1=phrase,
                    query_str2=filters,
                    itemtypes=('hm', ),
                    limit=None,
                    merge=False)
            self._timerUpdateIndex.start(0)

        if self._fts_hwdphr and self._fts_defexa:
            urlquery = QUrlQuery()
            if phrase:
                urlquery.addQueryItem("phrase", phrase)
            if filters:
                urlquery.addQueryItem("filters", filters)
            if mode:
                urlquery.addQueryItem("mode", mode)
            url = QUrl("search:///")
            url.setQuery(urlquery)
            self._ui.webView.load(url)


    def _onSearchExamples(self):
        query_str = self._ui.lineEditSearch.text().strip()
        self.fullSearch(query_str, None, mode='examples', only_web=True)
        self._ui.actionSearchExamples.setEnabled(False)


    def _onSearchDefinitions(self):
        query_str = self._ui.lineEditSearch.text().strip()
        self.fullSearch(query_str, None, mode='definitions', only_web=True)
        self._ui.actionSearchDefinitions.setEnabled(False)


    def _onAdvancedSearch(self):
        self._advsearch_window.show()
        self._advsearch_window.raise_()


    #---------------
    # Search Phrase
    #---------------

    def searchSelectedText(self):
        text = self._ui.webView.page().selectedText().strip()
        if len(text) > 100:
            text = ''.join(text[:100].rsplit(None, 1)[:1])
        self._ui.lineEditSearch.setText(text)
        self._instantSearch(pending=True, delay=False)

    def _onMonitorClipboardChanged(self):
        get_config()['monitorClipboard'] = \
                self._ui.actionMonitorClipboard.isChecked()

    def _onPaste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text(QClipboard.Clipboard)
        self._ui.lineEditSearch.setText(text)
        self._instantSearch(pending=True, delay=False)

    def _onClipboardChanged(self, mode):
        if self.isActiveWindow():
            return
        if not get_config().get('monitorClipboard', False):
            return

        clipboard = QApplication.clipboard()
        if mode == QClipboard.Selection:
            text = clipboard.text(QClipboard.Selection)
        elif mode == QClipboard.Clipboard:
            text = clipboard.text(QClipboard.Clipboard)
        #elif mode == QClipboard.FindBuffer:
        #    text = clipboard.text(QClipboard.FindBuffer)
        else:
            return

        text = ' '.join(text[:100].splitlines()).strip()
        res = self._incremental_search(text)
        if res:
            self._ui.lineEditSearch.setText(text)
            self._instantSearch(pending=True, delay=False)

    #-------------
    # Nav Buttons
    #-------------

    def _onNavForward(self):
        self._ui.webView.page().triggerAction(QWebPage.Forward)

    def _onNavBack(self):
        self._ui.webView.page().triggerAction(QWebPage.Back)

    def _onNavActionChanged(self):
        webPage = self._ui.webView.page()
        ui = self._ui
        ui.toolButtonNavForward.setEnabled(
            webPage.action(QWebPage.Forward).isEnabled())
        ui.toolButtonNavBack.setEnabled(
            webPage.action(QWebPage.Back).isEnabled())


    #-----------
    # Auto Pron
    #-----------

    def _autoPronPlayback(self):
        self._timerAutoPron.start(_INTERVAL_AUTO_PRON)


    def _onTimerAutoPronTimeout(self):
        autoplayback = get_config().get('autoPronPlayback', None)
        if autoplayback:
            metaData = self._ui.webView.page().mainFrame().metaData()
            if autoplayback == 'US' and ('us_pron' in metaData):
                self._playbackAudio('/us_hwd_pron/' + metaData['us_pron'][0])
            elif autoplayback == 'GB' and ('gb_pron' in metaData):
                self._playbackAudio('/gb_hwd_pron/' + metaData['gb_pron'][0])


    def _onAutoPronChanged(self, action):
        config = get_config()
        if action == self._ui.actionPronUS:
            config['autoPronPlayback'] = 'US'
        elif action == self._ui.actionPronGB:
            config['autoPronPlayback'] = 'GB'
        else:
            config['autoPronPlayback'] = ''


    #-----------
    # Find
    #-----------

    def setFindbarVisible(self, visible):
        ui = self._ui
        curr_visible = ui.frameFindbar.isVisible()
        ui.frameFindbar.setVisible(visible)

        if visible:
            ui.lineEditFind.setFocus()
            ui.lineEditFind.selectAll()
            text = ui.lineEditFind.text()
            if text:
                self.findText(text)
            else:
                ui.actionFindNext.setEnabled(False)
                ui.actionFindPrev.setEnabled(False)
        elif curr_visible:
            self.findText('')


    def findText(self, text):
        self._ui.actionFindNext.setEnabled(bool(text))
        self._ui.actionFindPrev.setEnabled(bool(text))

        findtext = self._ui.webView.findText
        findtext('')
        findtext('', QWebPage.HighlightAllOccurrences)
        found = findtext(text, QWebPage.HighlightAllOccurrences)
        self._ui.actionFindNext.setEnabled(found)
        self._ui.actionFindPrev.setEnabled(found)
        if found:
            findtext(text, QWebPage.FindWrapsAroundDocument)
        if found or not text:
            style = 'QLineEdit{ background-color: auto; color: auto; }'
        else:
            style = 'QLineEdit { background-color: #f77; color: white; }'
        self._ui.lineEditFind.setStyleSheet(style)


    def findNext(self):
        self._ui.webView.findText(
                self._ui.lineEditFind.text(),
                QWebPage.FindWrapsAroundDocument)


    def findPrev(self):
        self._ui.webView.findText(
                self._ui.lineEditFind.text(),
                QWebPage.FindBackward | QWebPage.FindWrapsAroundDocument)


    #-------
    # Print
    #-------

    def printPreview(self):
        ui = self._ui
        printer = self._printer
        printer.setDocName(ui.webView.title() or '')
        dialog = QPrintPreviewDialog(printer, self)
        dialog.paintRequested.connect(ui.webView.print_)
        dialog.exec_()


    def print_(self):
        ui = self._ui
        printer = self._printer
        printer.setDocName(ui.webView.title() or '')
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QDialog.Accepted:
            ui.webView.print_(printer)


    #------------
    # Debugging
    #------------

    def setInspectorVisible(self, visible):
        ui = self._ui
        ui.webInspector.setVisible(visible)
        ui.inspectorContainer.setVisible(visible)


    #-------
    # Help
    #-------

    def _onHelp(self):
        webbrowser.open(_HELP_PAGE_URL)


    def _onAbout(self):
        self._ui.webView.load(QUrl('static:///documents/about.html'))


    #----------
    # Indexer
    #----------

    def _check_index(self):
        config = get_config()
        if 'dataDir' in config:
            if config.get('versionIndexed', '') < _INDEX_SUPPORTED:
                # Index is obsolete
                msg = ("The format of the index files has been changed.\n"
                       "Please recreate the index database.")
            elif not is_ldoce5_dir(config['dataDir']):
                # dataDir has been dissapeared
                msg = ("The 'ldoce5.data' folder is not found at '{0}'.\n"
                       "Please recreate the index database.".format(
                              config.get('dataDir', '')))
            else:
                return
        else:
            # not exist yet
            msg = ("This application has to construct an index database"
                    " before you can use it.\n"
                   "Create now?\n"
                   "(It will take 3-10 minutes, "
                   "depending on the speed of your machine)")

        r = QMessageBox.question(self, "Welcome to the LDOCE5 Viewer", msg,
                QMessageBox.Yes|QMessageBox.Cancel, QMessageBox.Yes)
        if r == QMessageBox.Yes:
            self._show_indexer_dialog(autostart=True)
        else:
            self.close()


    def _show_indexer_dialog(self, autostart=False):
        """Show the Create Index dialog"""
        config = get_config()

        # Disable clipboard monitoring
        mc_enabled = config.get('monitorClipboard', False)
        config['monitorClipboard'] = False

        # Show the indexer dialog
        self._unload_searchers()
        dialog = IndexerDialog(self, autostart)
        if dialog.exec_():
            config.save()
            text = "welcome"
            self._ui.lineEditSearch.setText(text)
            self._instantSearch(pending=True, delay=False)

        # Restore the value of monitorClipboard
        config['monitorClipboard'] = mc_enabled

    #-------
    # Setup
    #-------

    def _setup_ui(self):
        ui = self._ui = Ui_MainWindow()
        ui.setupUi(self)

        wv = ui.webView
        wp = wv.page()

        self._ui.labelSearching.hide()

        # Toolbar
        toolBar = ui.toolBar
        toolBar.toggleViewAction().setVisible(False)
        toolBar.setIconSize(QSize(24, 24))
        ui.actionNavBack = QAction(self)
        ui.actionNavBack.setToolTip("Go Back")
        ui.toolButtonNavBack = ToolButton()
        ui.toolButtonNavBack.setDefaultAction(ui.actionNavBack)
        ui.actionNavForward = QAction(self)
        ui.actionNavForward.setToolTip("Go Forward")
        ui.toolButtonNavForward = ToolButton()
        ui.toolButtonNavForward.setDefaultAction(ui.actionNavForward)
        ui.lineEditSearch = LineEdit(self)
        ui.lineEditSearch.setPlaceholderText("Search...")
        ui.lineEditSearch.setInputMethodHints(
                Qt.ImhUppercaseOnly | Qt.ImhLowercaseOnly | Qt.ImhDigitsOnly)
        toolBar.addWidget(ui.toolButtonNavBack)
        toolBar.addWidget(ui.toolButtonNavForward)
        toolBar.addWidget(ui.lineEditSearch)
        toolBar.addAction(ui.actionSearchDefinitions)
        toolBar.addAction(ui.actionSearchExamples)
        toolBar.addAction(ui.actionAdvancedSearch)

        # Icons
        def _set_icon(obj, name=None, var_suffix=''):
            if name:
                icon = QIcon.fromTheme(name,
                        QIcon(':/icons/' + name + var_suffix + '.png'))
                obj.setIcon(icon)
            else:
                obj.setIcon(QIcon())

        self.setWindowIcon(QIcon(":/icons/icon.png"))
        _set_icon(ui.actionFindClose, 'window-close')
        _set_icon(ui.actionNavForward, 'go-next', '24')
        _set_icon(ui.actionNavBack, 'go-previous', '24')
        _set_icon(ui.actionFindNext, 'go-down')
        _set_icon(ui.actionFindPrev, 'go-up')
        _set_icon(ui.actionCloseInspector, 'window-close')
        ui.actionSearchDefinitions.setIcon(QIcon())
        ui.actionSearchExamples.setIcon(QIcon())

        if not _IS_OSX:
            _set_icon(ui.actionCreateIndex, 'document-properties')
            _set_icon(ui.actionFind, 'edit-find')
            _set_icon(ui.actionQuit, 'application-exit')
            _set_icon(ui.actionZoomIn, 'zoom-in')
            _set_icon(ui.actionZoomOut, 'zoom-out')
            _set_icon(ui.actionNormalSize, 'zoom-original')
            _set_icon(ui.actionHelp, 'help-contents')
            _set_icon(ui.actionAbout, 'help-about')
            _set_icon(ui.actionPrint, 'document-print')
            _set_icon(ui.actionPrintPreview, 'document-print-preview')
            _set_icon(wp.action(QWebPage.Forward), 'go-next', '24')
            _set_icon(wp.action(QWebPage.Back), 'go-previous', '24')
            _set_icon(wp.action(QWebPage.Reload), 'reload')
            _set_icon(wp.action(QWebPage.CopyImageToClipboard), 'edit-copy')
            _set_icon(wp.action(QWebPage.InspectElement), 'document-properties')
        else:
            ui.toolBar.setIconSize(QSize(16,16))
            ui.actionNavForward.setIcon(QIcon(":/icons/go-next-mac.png"))
            ui.actionNavBack.setIcon(QIcon(":/icons/go-previous-mac.png"))
            _set_icon(wp.action(QWebPage.Forward))
            _set_icon(wp.action(QWebPage.Back))
            _set_icon(wp.action(QWebPage.Reload))

        ui.frameFindbar.setStyleSheet("""#frameFindbar {
            border: 0px solid transparent;
            border-bottom: 1px solid palette(dark);
            background-color: qlineargradient(spread:pad,
            x1:0, y1:0, x2:0, y2:1,
            stop:0 palette(midlight), stop:1 palette(window));
            }""")

        ui.labelSearching.setStyleSheet("""#labelSearching {
            background-color: qlineargradient(spread:pad,
            x1:0, y1:0, x2:0, y2:1,
            stop:0 palette(midlight), stop:1 palette(window));
            }""")

        if _IS_OSX:
            self._ui.splitter.setStyleSheet("""
                #splitter::handle:horizontal {
                    border-right: 1px solid palette(dark);
                    width: 2px;
                }
                #splitter::handle:vertical {
                    border-bottom: 1px solid palette(dark);
                    height: 2px;
                }""")
            #ui.toolButtonCloseFindbar.setStyleSheet(
            #        "QToolButton {border: none;}")
            #ui.toolButtonCloseInspector.setStyleSheet(
            #        "QToolButton {border: none;}")
            #ui.toolButtonFindNext.setStyleSheet("QToolButton {border: none;}")
            #ui.toolButtonFindPrev.setStyleSheet("QToolButton {border: none;}")

        # Nav Buttons
        ui.actionNavForward.triggered.connect(self._onNavForward)
        ui.actionNavBack.triggered.connect(self._onNavBack)
        wp.action(QWebPage.Forward).changed.connect(self._onNavActionChanged)
        wp.action(QWebPage.Back).changed.connect(self._onNavActionChanged)

        # ListView
        ui.listWidgetIndex.setAttribute(Qt.WA_MacShowFocusRect, False);

        # WebView
        wp.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        QWebSettings.setMaximumPagesInCache(32)
        wv.history().setMaximumItemCount(50)
        for name in _LOCAL_SCHEMES:
            QWebSecurityOrigin.addLocalScheme(name)

        for web_act in (QWebPage.OpenLinkInNewWindow,
                QWebPage.OpenFrameInNewWindow, QWebPage.OpenImageInNewWindow,
                QWebPage.DownloadLinkToDisk, QWebPage.DownloadImageToDisk,
                QWebPage.CopyLinkToClipboard, QWebPage.CopyImageToClipboard,
                ):
            wp.action(web_act).setEnabled(False)
            wp.action(web_act).setVisible(False)

        if hasattr(QWebPage, 'CopyImageUrlToClipboard'):
            wp.action(QWebPage.CopyImageUrlToClipboard).setEnabled(False)
            wp.action(QWebPage.CopyImageUrlToClipboard).setVisible(False)

        ui.menuEdit.insertAction(ui.actionFind, wv.actionCopyPlain)
        ui.menuEdit.insertSeparator(ui.actionFind)

        self.addAction(wv.actionSearchText)
        wv.actionSearchText.setShortcut(QKeySequence('Ctrl+E'))

        # Web Inspector
        wp.settings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
        wp.action(QWebPage.InspectElement).setText('Inspect Element')
        ui.webInspector.setPage(wp)
        self.setInspectorVisible(False)

        # History Menu
        ui.menuBackHistory = QMenu(ui.toolButtonNavBack)
        ui.menuForwardHistory = QMenu(ui.toolButtonNavForward)
        ui.toolButtonNavBack.setMenu(ui.menuBackHistory)
        ui.toolButtonNavForward.setMenu(ui.menuForwardHistory)
        ui.menuBackHistory.setEnabled(False)
        ui.menuForwardHistory.setEnabled(False)

        # Signal -> Slot
        ui.lineEditSearch.textChanged.connect(self._onTextChanged)
        ui.lineEditSearch.textEdited.connect(self._onTextEdited)
        ui.lineEditFind.textChanged.connect(self.findText)
        ui.lineEditFind.returnPressed.connect(self.findNext)
        ui.lineEditFind.escapePressed.connect(
                partial(self.setFindbarVisible, visible=False))
        ui.lineEditFind.shiftReturnPressed.connect(self.findPrev)
        ui.listWidgetIndex.itemSelectionChanged.connect(
                self._onItemSelectionChanged)
        wp.linkClicked.connect(self._onWebViewLinkClicked)
        wv.loadStarted.connect(partial(self.setFindbarVisible, visible=False))
        wv.wheelWithCtrl.connect(self._onWebViewWheelWithCtrl)
        wv.urlChanged.connect(self._onUrlChanged)
        wv.loadFinished.connect(self._onLoadFinished)

        # Actions
        def act_conn(action, slot):
            action.triggered.connect(slot)

        act_conn(ui.actionAbout, self._onAbout)
        act_conn(ui.actionHelp, self._onHelp)
        act_conn(ui.actionCreateIndex, self._show_indexer_dialog)
        act_conn(ui.actionFindNext, self.findNext)
        act_conn(ui.actionFindPrev, self.findPrev)
        act_conn(ui.actionPrintPreview, self.printPreview)
        act_conn(ui.actionFocusLineEdit, self._onFocusLineEdit)
        act_conn(ui.actionPrint, self.print_)
        act_conn(ui.actionSearchExamples, self._onSearchExamples)
        act_conn(ui.actionSearchDefinitions, self._onSearchDefinitions)
        act_conn(ui.actionAdvancedSearch, self._onAdvancedSearch)
        act_conn(wv.actionSearchText, self.searchSelectedText)
        act_conn(wv.actionDownloadAudio, self.downloadSelectedAudio)
        act_conn(ui.actionZoomIn, partial(self.setZoom, 1, relative=True))
        act_conn(ui.actionZoomOut, partial(self.setZoom, -1, relative=True))
        act_conn(ui.actionNormalSize, partial(self.setZoom, 0))
        act_conn(ui.actionMonitorClipboard, self._onMonitorClipboardChanged)
        act_conn(ui.actionFind,
                partial(self.setFindbarVisible, visible=True))
        act_conn(ui.actionFindClose,
                partial(self.setFindbarVisible, visible=False))
        act_conn(ui.actionCloseInspector,
                partial(self.setInspectorVisible, visible=False))
        act_conn(wp.action(QWebPage.InspectElement),
                partial(self.setInspectorVisible, visible=True))

        ui.actionGroupAutoPron = QActionGroup(self)
        ui.actionGroupAutoPron.addAction(ui.actionPronOff)
        ui.actionGroupAutoPron.addAction(ui.actionPronGB)
        ui.actionGroupAutoPron.addAction(ui.actionPronUS)
        ui.actionGroupAutoPron.setExclusive(True)
        ui.actionGroupAutoPron.triggered.connect(self._onAutoPronChanged)

        self.addAction(ui.actionFocusLineEdit)
        self.addAction(wp.action(QWebPage.SelectAll))

        # Set an action to each ToolButton
        ui.toolButtonFindNext.setDefaultAction(ui.actionFindNext)
        ui.toolButtonFindPrev.setDefaultAction(ui.actionFindPrev)
        ui.toolButtonCloseFindbar.setDefaultAction(ui.actionFindClose)
        ui.toolButtonCloseInspector.setDefaultAction(ui.actionCloseInspector)

        actionPaste = QAction(self)
        actionPaste.triggered.connect(self._onPaste)
        actionPaste.setShortcut(QKeySequence('Ctrl+V'))
        self.addAction(actionPaste)

        # Shorcut keys
        ui.actionQuit.setShortcuts(QKeySequence.Quit)
        ui.actionHelp.setShortcuts(QKeySequence.HelpContents)
        ui.actionFind.setShortcuts(QKeySequence.Find)
        ui.actionFindNext.setShortcuts(QKeySequence.FindNext)
        ui.actionFindPrev.setShortcuts(QKeySequence.FindPrevious)
        ui.actionZoomIn.setShortcuts(QKeySequence.ZoomIn)
        ui.actionZoomOut.setShortcuts(QKeySequence.ZoomOut)
        ui.actionPrint.setShortcuts(QKeySequence.Print)
        ui.actionNormalSize.setShortcut(QKeySequence('Ctrl+0'))
        ui.actionFocusLineEdit.setShortcut(QKeySequence('Ctrl+L'))
        wp.action(QWebPage.SelectAll).setShortcut(QKeySequence('Ctrl+A'))
        wp.action(QWebPage.Back).setShortcuts([
            k for k in QKeySequence.keyBindings(QKeySequence.Back)
                if not k.matches(QKeySequence("Backspace"))])
        wp.action(QWebPage.Forward).setShortcuts(
            [k for k in QKeySequence.keyBindings(QKeySequence.Forward)
                if not k.matches(QKeySequence("Shift+Backspace"))])
        ui.actionNavBack.setShortcuts([
            k for k in QKeySequence.keyBindings(QKeySequence.Back)
                if not k.matches(QKeySequence("Backspace"))] +
                [QKeySequence("Ctrl+[")])
        ui.actionNavForward.setShortcuts(
            [k for k in QKeySequence.keyBindings(QKeySequence.Forward)
                if not k.matches(QKeySequence("Shift+Backspace"))] +
                [QKeySequence("Ctrl+]")])

        # Reset
        self._updateTitle('')
        self._updateIndex()
        self.setFindbarVisible(False)
        self._onTextChanged(self._ui.lineEditSearch.text())
        self._onNavActionChanged()


    #----------------
    # Configurations
    #----------------

    def _restore_from_config(self):
        ui = self._ui
        config = get_config()
        try:
            if 'windowGeometry' in config:
                self.restoreGeometry(config['windowGeometry'])
            if 'splitterSizes' in config:
                ui.splitter.restoreState(config['splitterSizes'])
        except:
            pass

        try:
            pron = config.get('autoPronPlayback', None)
            acts = {'US': self._ui.actionPronUS,
                    'GB': self._ui.actionPronGB }
            acts.get(pron, self._ui.actionPronOff).setChecked(True)
        except:
            pass

        try:
            ui.actionMonitorClipboard.setChecked(
                config.get('monitorClipboard', False))
        except:
            pass

        try:
            self.setZoom(0, relative=True)
        except:
            pass


    def _save_to_configfile(self):
        config = get_config()
        config['windowGeometry'] = bytes(self.saveGeometry())
        config['splitterSizes'] = bytes(self._ui.splitter.saveState())
        config.save()


    #-----------------
    # Resource Loader
    #-----------------

    def _updateNetworkAccessManager(self, fulltext_hp, fulltext_de):
        nwaccess = MyNetworkAccessManager(self, fulltext_hp, fulltext_de)
        webPage = self._ui.webView.page()
        webPage.setNetworkAccessManager(nwaccess)
        self._networkAccessManager = nwaccess

    def _unload_searchers(self):
        self._updateNetworkAccessManager(None, None)

        obj = self._lazy.pop(_LAZY_FTS_HWDPHR_ASYNC, None)
        if obj:
            obj.shutdown()

        obj = self._lazy.pop(_LAZY_FTS_HWDPHR, None)
        if obj:
            obj.close()

        obj = self._lazy.pop(_LAZY_FTS_DEFEXA, None)
        if obj:
            obj.close()

        obj = self._lazy.pop(_LAZY_INCREMENTAL, None)
        if obj:
            obj.close()

    @property
    def _fts_hwdphr(self):
        obj = self._lazy.get(_LAZY_FTS_HWDPHR, None)
        if obj is None:
            config = get_config()
            try:
                obj = self._lazy[_LAZY_FTS_HWDPHR] = fulltext.Searcher(
                        config.fulltext_hwdphr_path, config.variations_path)
            except (EnvironmentError, fulltext.IndexError):
                pass
            self._updateNetworkAccessManager(
                    self._lazy.get(_LAZY_FTS_HWDPHR, None),
                    self._lazy.get(_LAZY_FTS_DEFEXA, None))

        return obj

    @property
    def _fts_defexa(self):
        obj = self._lazy.get(_LAZY_FTS_DEFEXA, None)
        if obj is None:
            config = get_config()
            try:
                obj = self._lazy[_LAZY_FTS_DEFEXA] = \
                        fulltext.Searcher(
                            config.fulltext_defexa_path,
                            config.variations_path)
            except (EnvironmentError, fulltext.IndexError):
                pass
            self._updateNetworkAccessManager(
                    self._lazy.get(_LAZY_FTS_HWDPHR, None),
                    self._lazy.get(_LAZY_FTS_DEFEXA, None))

        return obj

    @property
    def _fts_hwdphr_async(self):
        obj = self._lazy.get(_LAZY_FTS_HWDPHR_ASYNC, None)
        if obj is None:
            searcher = self._fts_hwdphr
            if searcher:
                obj = self._lazy[_LAZY_FTS_HWDPHR_ASYNC] = \
                        AsyncFTSearcher(self, searcher)
                obj.finished.connect(self._onAsyncFTSearchFinished)
                obj.error.connect(self._onAsyncFTSearchError)

        return obj

    @property
    def _incremental(self):
        obj = self._lazy.get(_LAZY_INCREMENTAL, None)
        if obj is None:
            try:
                obj = self._lazy[_LAZY_INCREMENTAL] = incremental.Searcher(
                        get_config().incremental_path)
            except (EnvironmentError, incremental.IndexError):
                pass

        return obj

    @property
    def _soundplayer(self):
        obj = self._lazy.get(_LAZY_SOUNDPLAYER, None)
        if obj is None:
            obj = self._lazy[_LAZY_SOUNDPLAYER] = \
                    create_soundplayer(self, get_config()._data_dir)

        return obj

    @property
    def _advsearch_window(self):
        obj = self._lazy.get(_LAZY_ADVSEARCH_WINDOW, None)
        if obj is None:
            obj = self._lazy[_LAZY_ADVSEARCH_WINDOW] = \
                    AdvancedSearchDialog(self)

        return obj

    @property
    def _printer(self):
        obj = self._lazy.get(_LAZY_PRINTER, None)
        if obj is None:
            obj = self._lazy[_LAZY_PRINTER] = QPrinter()

        return obj

