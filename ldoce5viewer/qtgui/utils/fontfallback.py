'''My very own font fallback facility

(QtWebkit 2.2 doesn't perform the font fallback properly because of a bug)
'''

import re

from PyQt5.QtGui import QFont


_DEFAULT_FONT_NAMES = frozenset((b'sans-serif', b'serif', b'monospace'))


def _fallback(fontnames):
    for name in fontnames:
        if name in _DEFAULT_FONT_NAMES:
            return name
        elif QFont(name).exactMatch():
            return name
    return 'serif'


def css_replace_fontfamily(text):
    def replace_func(m):
        families = (s.strip().strip('"\'') for s in m.group(2).split(','))
        return ''.join((
            m.group(1),
            'font-family: "',
            _fallback(families),
            '"',
            m.group(3)))

    return re.sub(r"({|;)\s*font-family\s*:\s*(.*?)(;|})",
                  replace_func, text, flags=re.MULTILINE | re.DOTALL)
