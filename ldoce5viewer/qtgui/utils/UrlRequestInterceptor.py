from PySide6.QtCore import QUrlQuery
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo


class UrlRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        self._main_window = parent
        super().__init__(parent)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo):
        url = info.requestUrl()
        if url.scheme() == "audio":
            self._main_window._playback_audio(url.path())
        elif url.scheme() == "lookup":
            query = dict((k, v) for (k, v) in QUrlQuery(url).queryItems())
            if "q" in query:
                q = query["q"].replace("+", " ")
                self._main_window._ui.lineEditSearch.setText(q)
                self._main_window._instantSearch(pending=True, delay=False)