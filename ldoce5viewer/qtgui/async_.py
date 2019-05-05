"""Asynchlonous full-text search facility for phrase search"""

from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from PyQt5.QtCore import (
    QObject, QThread, QMutex, QWaitCondition, pyqtSignal)

_logger = logging.getLogger(__name__)


class _FTSearchThread(QThread):
    '''This thread performs full text search in the background'''

    searchFinished = pyqtSignal()
    searchError = pyqtSignal()

    def __init__(self, searcher, parent):
        QThread.__init__(self, parent)
        self._searcher = searcher
        self._quit = False
        self._mutex = QMutex()
        self._pending = QWaitCondition()
        self._collector = None
        self._query = None
        self._result = None

    def run(self):
        while not self._quit:
            self._mutex.lock()
            if not self._query:
                self._pending.wait(self._mutex)
            query = self._query
            self._query = None
            self._mutex.unlock()

            # search
            if query:
                (query_str1, query_str2, itemtypes,
                 limit, highlight, merge) = query

                self._mutex.lock()
                collector = self._searcher.make_collector(limit)
                self._collector = collector
                self._mutex.unlock()

                try:
                    result = self._searcher.search(
                        collector,
                        query_str1, query_str2,
                        itemtypes, highlight)
                except:
                    self._mutex.lock()
                    self._result = None
                    self._mutex.unlock()
                    self.searchError.emit()
                else:
                    if collector.aborted:
                        pass
                    else:
                        self._mutex.lock()
                        self._result = (merge, result)
                        self._mutex.unlock()
                        self.searchFinished.emit()

                self._mutex.lock()
                self._collector = None
                self._mutex.unlock()

    def cancel(self):
        self._mutex.lock()
        self._query = None
        if self._collector:
            self._collector.abort()
        self._mutex.unlock()

    def quit(self):
        self._mutex.lock()
        if self._collector:
            self._collector.abort()
        self._query = None
        self._quit = True
        self._mutex.unlock()
        self._pending.wakeAll()

    def update_query(self, query_str1=None, query_str2=None, itemtypes=(),
                     limit=1000, highlight=False, merge=False):
        self._mutex.lock()
        if self._collector:
            self._collector.abort()
        self._query = (query_str1, query_str2,
                       itemtypes, limit, highlight, merge)
        self._mutex.unlock()
        self._pending.wakeAll()

    def take_result(self):
        self._mutex.lock()
        r = self._result
        self._result = None
        self._mutex.unlock()
        return r


class AsyncFTSearcher(QObject):
    finished = pyqtSignal()
    error = pyqtSignal()

    def __init__(self, parent, searcher):
        QObject.__init__(self, parent)

        self._result = None
        self._thread = _FTSearchThread(searcher, self)
        self._thread.searchFinished.connect(self._onFinished)
        self._thread.searchError.connect(self._onError)
        self._thread.start()

    def update_query(self, query_str1=None, query_str2=None, itemtypes=(),
                     limit=1000, highlight=False, merge=False):
        self._thread.update_query(query_str1, query_str2, itemtypes,
                                  limit, highlight, merge)

    def shutdown(self):
        self._thread.quit()
        self._thread.wait()
        self._thread = None

    def cancel(self):
        self._thread.cancel()

    def _onError(self):
        self.error.emit()

    def _onFinished(self):
        if self._thread:
            self._result = self._thread.take_result()
            self.finished.emit()

    def take_result(self):
        r = self._result
        self._result = None
        return r
