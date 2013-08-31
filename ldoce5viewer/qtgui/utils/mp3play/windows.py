from __future__ import unicode_literals, absolute_import, print_function

import random
from ctypes import windll, c_buffer



class _MCI:
    def __init__(self):
        self.w32mci = windll.winmm.mciSendStringA
        self.w32mcierror = windll.winmm.mciGetErrorStringA

    def send(self, command):
        buffer = c_buffer(255)
        errorcode = self.w32mci(str(command), buffer, 254, 0)
        if errorcode:
            return errorcode, self.get_error(errorcode)
        else:
            return errorcode, buffer.value

    def get_error(self, error):
        error = int(error)
        buffer = c_buffer(255)
        self.w32mcierror(error, buffer, 254)
        return buffer.value

    def directsend(self, txt):
        (err, buf) = self.send(txt)
        if err != 0:
            print('Error %s for "%s": %s' % (str(err), txt, buf))
        return (err, buf)


# TODO: detect errors in all mci calls
class AudioClip(object):
    def __init__(self, filename):
        filename = filename.replace('/', '\\')
        self.filename = filename
        self._alias = 'mp3_%s' % repr(random.random())

        self._mci = _MCI()

        (err, buf) = self._mci.directsend(
                r'open "%s" alias %s' % (filename, self._alias ))
        if err:
            raise Exception(buf)

        (err, buf) = self._mci.directsend(
                'set %s time format milliseconds' % self._alias)
        if err:
            raise Exception(buf)

        (err, buf) = self._mci.directsend(
                'status %s length' % self._alias)
        if err:
            raise Exception(buf)

        self._length_ms = int(buf)

    def volume(self, level):
        """Sets the volume between 0 and 100."""
        self._mci.directsend('setaudio %s volume to %d' %
                (self._alias, level * 10) )

    def play(self, start_ms=None, end_ms=None):
        start_ms = 0 if not start_ms else start_ms
        end_ms = self.milliseconds() if not end_ms else end_ms
        err,buf=self._mci.directsend('play %s from %d to %d'
                % (self._alias, start_ms, end_ms) )

    def isplaying(self):
        return self._mode() == 'playing'

    def _mode(self):
        err, buf = self._mci.directsend('status %s mode' % self._alias)
        return buf

    def pause(self):
        self._mci.directsend('pause %s' % self._alias)

    def unpause(self):
        self._mci.directsend('resume %s' % self._alias)

    def ispaused(self):
        return self._mode() == 'paused'

    def stop(self):
        self._mci.directsend('stop %s' % self._alias)
        self._mci.directsend('seek %s to start' % self._alias)

    def close(self):
        if self._alias is not None:
            self._mci.directsend('close %s' % self._alias)
            self._alias = None

    def milliseconds(self):
        return self._length_ms

    # TODO: this closes the file even if we're still playing.
    # no good.  detect isplaying(), and don't die till then!
    def __del__(self):
        self.close()

