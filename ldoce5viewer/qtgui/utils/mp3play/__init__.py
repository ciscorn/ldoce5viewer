import os

if os.name == 'nt':
    from .windows import AudioClip as _PlatformSpecificAudioClip
else:
    raise Exception("mp3play can't run on your operating system.")

def load(filename):
    """Return an AudioClip for the given filename."""
    return AudioClip(filename)

class AudioClip(object):
    __slots__ = ['_clip']

    def __init__(self, filename):
        """Create an AudioClip for the given filename."""
        self._clip = _PlatformSpecificAudioClip(filename)

    def play(self, start_ms=None, end_ms=None):
        """
        Start playing the audio clip, and return immediately. Play from
        start_ms to end_ms if either is specified; defaults to beginning
        and end of the clip.  Returns immediately.  If end_ms is specified
        as smaller than start_ms, nothing happens.
        """
        if end_ms != None and end_ms < start_ms:
            return
        else:
            return self._clip.play(start_ms, end_ms)

    def volume(self, level):
        """Sets the volume between 0 and 100."""
        assert level >=0 and level <= 100
        return self._clip.volume(level)

    def isplaying(self):
        """Returns True if the clip is currently playing.  Note that if a
        clip is paused, or if you called play() on a clip and playing has
        completed, this returns False."""
        return self._clip.isplaying()

    def pause(self):
        """Pause the clip if it is currently playing."""
        return self._clip.pause()

    def unpause(self):
        """Unpause the clip if it is currently paused."""
        return self._clip.unpause()

    def ispaused(self):
        """Returns True if the clip is currently paused."""
        return self._clip.ispaused()

    def stop(self):
        """Stop the audio clip if it is playing."""
        return self._clip.stop()

    def close(self):
        """Stop the audio clip if it is playing."""
        return self._clip.close()

    def seconds(self):
        """
        Returns the length in seconds of the audio clip, rounded to the
        nearest second.
        """
        return int(round(float(self.milliseconds()) / 1000))

    def milliseconds(self):
        """Returns the length in milliseconds of the audio clip."""
        return self._clip.milliseconds()
