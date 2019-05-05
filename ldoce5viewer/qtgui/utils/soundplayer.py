import sys
import os
import abc
from tempfile import NamedTemporaryFile, mkdtemp
import logging

from PyQt5.QtCore import *
from ...utils.compat import range

_logger = logging.getLogger(__name__)

# Gstreamer 1.0
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import GObject, Gst
    GObject.threads_init()
    Gst.init(None)
except (ImportError, ValueError):
    Gst = None
    GObject = None

# Gstreamer 0.10
try:
    if Gst is not None:
        raise ImportError()
    import gst
    import gobject
    gobject.threads_init()
except ImportError:
    gst = None
    gobject = None

# Cocoa via PyObjC
try:
    import AppKit
except:
    AppKit = None


# WinMCI
if sys.platform == 'win32':
    try:
        import mp3play
    except:
        mp3play = None
else:
    mp3play = None


# Qt-Phonon
try:
    from PyQt5.phonon import Phonon
except ImportError:
    Phonon = None


# Qt-Multimedia
try:
    import PyQt5.QtMultimedia as QtMultimedia
except ImportError:
    QtMultimedia = None


class Backend(object):
    __metaclass__ = abc.ABCMeta
    def __init__(self, parent, temp_dir):
        pass
    @abc.abstractmethod
    def play(self, data):
        pass
    @abc.abstractmethod
    def close(self):
        pass


class NullBackend(Backend):
    def __init__(self, parent, temp_dir):
        pass
    def play(self, data):
        pass
    def close(self):
        pass


class GstreamerBackend(Backend):
    """Backend for Gstreamer 1.0"""

    def __init__(self, parent, temp_dir):
        self._player = None
        self._data = None

    def play(self, data):
        if self._player:
            self._player.set_state(Gst.State.NULL)

        try:
            self._player = Gst.parse_launch(
                    'appsrc name=src ! decodebin ! autoaudiosink')
        except:
            _logger.error(
                "Gstreamer's good-plugins package is needed to play sound")
            return

        self._player.set_state(Gst.State.NULL)
        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)

        def need_data(appsrc, size):
            if not self._data:
                appsrc.emit('end-of-stream')
                return
            appsrc.emit('push-buffer', Gst.Buffer.new_wrapped(self._data[:size]))
            self._data = self._data[size:]

        self._data = data
        self._player.get_by_name('src').connect('need-data', need_data)
        self._player.set_state(Gst.State.PLAYING)

    def _on_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self._player.set_state(Gst.State.NULL)
            self._player = None

    def close(self):
        if self._player:
            self._player.set_state(Gst.State.NULL)
        self._player = None


class GstreamerOldBackend(Backend):
    """Backend for Gstreamer 0.10"""

    def __init__(self, parent, temp_dir):
        self._player = None
        self._data = None

    def play(self, data):
        if self._player:
            self._player.set_state(gst.STATE_NULL)

        try:
            self._player = gst.parse_launch(
                    'appsrc name=src ! decodebin2 ! autoaudiosink')
        except:
            _logger.error(
                "Gstreamer's good-plugins package is needed to play sound")
            return

        self._player.set_state(gst.STATE_NULL)
        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)

        def need_data(appsrc, size):
            if not self._data:
                appsrc.emit('end-of-stream')
                return
            appsrc.emit('push-buffer', gst.Buffer(self._data[:size]))
            self._data = self._data[size:]

        self._data = data
        self._player.get_by_name('src').connect('need-data', need_data)
        self._player.set_state(gst.STATE_PLAYING)

    def _on_message(self, bus, message):
        if message.type == gst.MESSAGE_EOS:
            self._player.set_state(gst.STATE_NULL)
            self._player = None

    def close(self):
        if self._player:
            self._player.set_state(gst.STATE_NULL)
        self._player = None


class WinMCIBackend(Backend):
    def __init__(self, parent, temp_dir):
        self._mp3 = None
        self._NUM_TRY = 30
        self._temp_dir = temp_dir

    def _get_f(self):
        for i in range(self._NUM_TRY):
            path = os.path.join(self._temp_dir,
                    "sound.tmp{0}.mp3".format(i))
            try:
                os.unlink(path)
            except:
                pass
            try:
                f = open(path, "wb")
            except IOError:
                continue
            else:
                return f
        return None

    def play(self, data):
        if self._mp3:
            self._mp3.stop()
            self._mp3.close()
            self._mp3 = None
        f = self._get_f()
        if f is None:
            return
        f.write(data)
        path = f.name
        f.close()
        self._mp3 = mp3play.load(path)
        self._mp3.play()

    def close(self):
        for i in range(self._NUM_TRY):
            path = os.path.join(self._temp_dir,
                    "sound.tmp{0}.mp3".format(i))
            try:
                os.unlink(path)
            except:
                pass


class PhononBackend(Backend):
    def __init__(self, parent, temp_dir):
        self._player = Phonon.createPlayer(Phonon.NoCategory)
        self._player.finished.connect(self._onFinished)
        self._alive = set()

    def _onFinished(self):
        self._clean_tmp()

    def _play(self):
        source = Phonon.MediaSource(self._path)
        self._player.setCurrentSource(source)
        self._player.play()

    def play(self, data):
        self._player.stop()
        self._clean_tmp()
        with NamedTemporaryFile(mode='w+b', prefix='',
                suffix='.tmp.mp3', delete=False) as f:
            f.write(data)
            self._path = f.name
            self._alive.add(f.name)
        QTimer.singleShot(0, self._play)

    def _clean_tmp(self):
        removed = []
        for path in self._alive:
            try:
                os.unlnk(path)
            except:
                pass
            else:
                removed.append(path)
        self._alive.difference_update(removed)

    def close(self):
        self._player.stop()
        self._clean_tmp()


class QtMultimediaBackend(Backend):
    def __init__(self, parent, temp_dir):
        self._player = QtMultimedia.QMediaPlayer()
        self._tmpdir = mkdtemp()

    def _play(self):
        url = QUrl.fromLocalFile(self._path)
        content = QtMultimedia.QMediaContent(url)
        self._player.setMedia(content)
        self._player.play()

    def play(self, data):
        self._player.stop()
        with NamedTemporaryFile(mode='w+b', prefix='',
                suffix='.tmp.mp3', dir=self._tmpdir, delete=False) as f:
            f.write(data)
            self._path = f.name
        QTimer.singleShot(0, self._play)

    def close(self):
        self._player.stop()


class AppKitBackend(Backend):
    def __init__(self, parent, temp_dir):
        self._sound = None

    def stop(self):
        if self._sound:
            self._sound.stop()

    def play(self, data):
        if self._sound:
            self._sound.stop()

        self._sound = AppKit.NSSound.alloc().initWithData_(data)
        self._sound.play()

    def close(self):
        self.stop()


def create_soundplayer(parent, temp_dir):
    backends = []
    if AppKit:
        backends.append(AppKitBackend)
    if mp3play:
        backends.append(WinMCIBackend)
    if Phonon:
        backends.append(PhononBackend)
    if QtMultimedia:
        backends.append(QtMultimediaBackend)
    if Gst:
        backends.append(GstreamerBackend)
    if gst:
        backends.append(GstreamerOldBackend)
    backends.append(NullBackend)

    return backends[0](parent, temp_dir)



