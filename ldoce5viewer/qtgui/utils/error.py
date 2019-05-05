"""Error console"""

from logging import StreamHandler

from PyQt5.QtCore import QMutex, QObject, pyqtSignal
from PyQt5.QtWidgets import QPlainTextEdit


class MyStreamHandler(StreamHandler):
    def __init__(self):
        StreamHandler.__init__(self)

    def createLock(self):
        # must be Recursive (= reentrant)
        self._mutex = QMutex(QMutex.Recursive)

    def acquire(self):
        self._mutex.lock()

    def release(self):
        self._mutex.unlock()


class StdErrWrapper(QObject):
    _write = pyqtSignal(type(u''))
    _flush = pyqtSignal()

    def __init__(self, old_stderr):
        QObject.__init__(self)
        self._old_stderr = old_stderr
        self._widget = None
        self._mutex = QMutex(QMutex.Recursive)

    def setApplication(self, app):
        assert(self._widget is None)

        widget = QPlainTextEdit()
        widget.setWindowTitle(u"Error Console")
        widget.resize(486, 300)
        widget.appendHtml(
            u'<span style="color: green">'
            u'An unhandled error occurred.<br>'
            u'Sorry for the inconvinience.<br>'
            u'Please copy the following text into a bug report:<br><br>'
            u'</span>')
        app.aboutToQuit.connect(self.restoreStdErr)
        self._write.connect(self._write_handler)
        self._flush.connect(self._flush_handler)
        self._widget = widget

    def _write_handler(self, data):
        self._mutex.lock()
        if self._widget:
            self._widget.show()
            self._widget.insertPlainText(data)
        self._mutex.unlock()

    def _flush_handler(self):
        self._mutex.lock()
        if self._widget:
            self._widget.show()
        self._mutex.unlock()

    def restoreStdErr(self):
        self._mutex.lock()
        if self._widget:
            self._widget.close()
            self._widget = None
        self._mutex.unlock()

    @property
    def encoding(self):
        return 'utf-8'

    def write(self, s):
        self._mutex.lock()
        if self._widget:
            if isinstance(s, bytes):
                s = s.decode('utf-8', 'replace')
            self._write.emit(s)
        else:
            self._old_stderr.write(s)
        self._mutex.unlock()

    def flush(self):
        self._mutex.lock()
        if self._widget:
            self._flush.emit()
        else:
            self._old_stderr.flush()
        self._mutex.unlock()
