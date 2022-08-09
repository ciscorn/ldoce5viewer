"""application-specific URI scheme handler for QtWebKit"""

import imp
import os.path
import sys
import traceback

from PySide6.QtCore import QBuffer, QUrl, QUrlQuery
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWebEngineCore import (
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)

from .. import __name__ as basepkgname
from .. import __version__
from ..ldoce5 import LDOCE5, ArchiveError, FilemapError, NotFoundError
from ..utils.text import enc_utf8
from .advanced import search_and_render
from .config import get_config

# from .utils import fontfallback

STATIC_REL_PATH = "static"

_static_cache = {}


def _load_static_data(filename):
    """Load a static file from the 'static' directory"""

    if filename in _static_cache:
        return _static_cache[filename]

    is_frozen = hasattr(sys, "frozen") or imp.is_frozen(  # new py2exe
        "__main__"
    )  # tools/freeze

    if is_frozen:
        if sys.platform.startswith("darwin"):
            path = os.path.join(
                os.path.dirname(sys.executable),
                "../Resources",
                STATIC_REL_PATH,
                filename,
            )
        else:
            path = os.path.join(
                os.path.dirname(sys.executable), STATIC_REL_PATH, filename
            )
        with open(path, "rb") as f:
            data = f.read()
    else:
        try:
            from pkgutil import get_data as _get
        except ImportError:
            from pkg_resources import resource_string as _get

        data = _get(basepkgname, os.path.join(STATIC_REL_PATH, filename))

    if filename.endswith(".css"):
        s = data.decode("utf-8")
        # s = fontfallback.css_replace_fontfamily(s)
        data = s.encode("utf-8")
    elif filename.endswith(".html"):
        s = data.decode("utf-8")
        s = s.replace("{% current_version %}", __version__)
        data = s.encode("utf-8")

    _static_cache[filename] = data
    return data


class MyUrlSchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, parent, searcher_hp=None, searcher_de=None):
        super().__init__(parent)
        self._searcher_hp = searcher_hp
        self._searcher_de = searcher_de
        config = get_config()
        self._ldoce5 = LDOCE5(config.get("dataDir", ""), config.filemap_path)

    def update_searcher(self, searcher_hp, searcher_de):
        self._searcher_hp = searcher_hp
        self._searcher_de = searcher_de

    def get_ldoce_content(self, path):
        (data, mime) = self._ldoce5.get_content(path)
        return (data, mime)

    def requestStarted(self, job: QWebEngineUrlRequestJob):
        url = job.requestUrl()
        scheme = url.scheme()
        mime = "text/html"
        data = b""

        if scheme == "dict":
            try:
                path = url.path().split("#", 1)[0]
                (data, mime) = self._ldoce5.get_content(path)
                mime = "text/html"
            except NotFoundError:
                data = b"<h2>Content Not Found</h2>"
                mime = "text/html"
            except FilemapError:
                data = b"<h2>File-Location Map Not Available</h2>"
                mime = "text/html"
            except ArchiveError:
                data = b"<h2>Dictionary Data Not Available</h2>"
                mime = "text/html"
        elif scheme == "static":
            try:
                data = _load_static_data(url.path().lstrip("/"))
                mime = ""
            except EnvironmentError:
                data = b"<h2>Static File Not Found</h2>"
                mime = "text/html"
        elif scheme == "search":
            searcher_hp = self._searcher_hp
            searcher_de = self._searcher_de
            if searcher_hp and searcher_de:
                try:
                    data = enc_utf8(search_and_render(url, searcher_hp, searcher_de))
                    mime = "text/html"
                except Exception:
                    s = u"<h2>Error</h2><div>{0}</div>".format(
                        "<br>".join(traceback.format_exc().splitlines())
                    )
                    data = enc_utf8(s)
                    mime = "text/html"
            else:
                mime = "text/html"
                data = b"<p>The full-text search index has not been created yet or broken.</p>"
        elif scheme == "audio":
            path = url.path().split("#", 1)[0]
            self.play_audio(path)
            return
        elif scheme == "lookup":
            query = dict((k, v) for (k, v) in QUrlQuery(url).queryItems())
            if "q" in query:
                q = query["q"].replace("+", " ")
                self.parent()._ui.lineEditSearch.setText(q)
                self.parent()._instantSearch(pending=True, delay=False)
        else:
            job.fail(QWebEngineUrlRequestJob.Error.RequestAborted)

        buffer = self.create_buffer(data, job)
        job.reply(mime.encode("ascii"), buffer)

    def create_buffer(self, data, parent):
        buffer = QBuffer(parent)
        buffer.open(QBuffer.OpenModeFlag.ReadWrite)
        buffer.write(data or b"")
        buffer.seek(0)
        return buffer

    def play_audio(self, path):
        (data, mime) = self._ldoce5.get_content(path)

        buffer = self.create_buffer(data, self.parent())
        audio_output = QAudioOutput(self.parent())
        player = QMediaPlayer(self.parent())
        player.setAudioOutput(audio_output)
        player.setSourceDevice(buffer, QUrl(path))
        player.play()
