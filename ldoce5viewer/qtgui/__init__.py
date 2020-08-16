'''Entry point for the application'''

from __future__ import unicode_literals, absolute_import, print_function

_SINGLEAPP_KEY = 'ed437af1-0388-4e13-90e9-486bdc88c77a'

from .. import __author__

# use PyQt API v2
import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

import sys
from optparse import OptionParser
import logging
import codecs
import os.path

from PyQt5.QtGui import QIcon

from .utils.singleapp import SingleApplication
from .utils.error import StdErrWrapper, MyStreamHandler
from .config import get_config


# set a dummy function if QLineEdit doesn't have setPlaceholderText
from PyQt5.QtWidgets import QLineEdit
if not hasattr(QLineEdit, 'setPlaceholderText'):
    def _dummySetPlaceholderText(self, *args, **kwargs):
        pass
    setattr(QLineEdit, 'setPlaceholderText', _dummySetPlaceholderText)


try:
    from . import ui
    from . import resources
except ImportError:
    print("need to run '$ make' in order for the program to work")
    exit()


def _setup_py2exe(config):
    # suspend py2exe's logging facility
    log_path = os.path.join(config._config_dir, 'log.txt')
    try:
        f = codecs.open(log_path, 'w', encoding='utf-8')
    except:
        pass
    else:
        sys.stderr = f


def run(argv):
    '''start the application'''

    config = get_config()

    # py2exe
    if sys.platform == 'win32' and \
            (hasattr(sys, 'frozen') or hasattr(sys, 'importers')):
        _setup_py2exe(config)

    # Parse arguments
    optparser = OptionParser()
    optparser.set_defaults(debug=False)
    optparser.add_option(
        '--debug', action='store_true', help='Enable debug mode')
    (options, args) = optparser.parse_args(argv)

    # stderr wrapper
    sys.stderr = StdErrWrapper(sys.stderr)

    # logging
    logger = logging.getLogger()
    handler = MyStreamHandler()
    handler.setFormatter(
        logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if options.debug else logging.ERROR)

    # Create an application instance
    app = SingleApplication(argv, _SINGLEAPP_KEY)
    if app.isRunning():
        app.sendMessage('activate')
        return 1

    # Load the configuration file
    config.debug = options.debug
    config.load()

    # Set the application's information
    app.setApplicationName(config.app_name)
    app.setOrganizationName(__author__)
    app.setWindowIcon(QIcon(':/icons/icon.png'))

    # Setup MainWindow
    from .main import MainWindow
    main_window = MainWindow()

    def messageHandler(msg):
        if msg == 'activate':
            main_window.activateWindow()
            main_window.setVisible(True)
    app.messageAvailable.connect(messageHandler)

    # On Windows-ja
    if app.font().family() == u'MS UI Gothic':
        cand = (('Segoe UI', None), ('Meiryo UI', None), ('Tahoma', 8))
        from PyQt5.QtGui import QFont
        for name, point in cand:
            ps = app.font().pointSize()
            if point is None:
                point = ps if ps != -1 else 9
            font = QFont(name, point)
            if font.exactMatch():
                app.setFont(font)
                break

    # Redirect stderr to the Error Console
    if not options.debug:
        sys.stderr.setApplication(app)

    # Start the application
    r = app.exec_()

    # Quit
    config.save()
    return r
