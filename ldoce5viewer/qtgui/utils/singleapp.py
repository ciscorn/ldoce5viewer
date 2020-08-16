'''This module prevent you from running two instances of the app'''


from PyQt5.QtCore import pyqtSignal, QIODevice
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QLocalSocket, QLocalServer


class SingleApplication(QApplication):
    messageAvailable = pyqtSignal(type(u''))

    def __init__(self, argv, key):
        QApplication.__init__(self, argv)

        self._key = key
        self._timeout = 1000

        socket = QLocalSocket(self)
        socket.connectToServer(self._key)
        if socket.waitForConnected(self._timeout):
            self._isRunning = True
            socket.abort()
            return
        socket.abort()

        self._isRunning = False
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self.__onNewConnection)
        self._server.listen(self._key)

        self.aboutToQuit.connect(self.__onAboutToQuit)

    def __onAboutToQuit(self):
        if self._server:
            self._server.close()
            self._server = None

    def __onNewConnection(self):
        socket = self._server.nextPendingConnection()
        if socket.waitForReadyRead(self._timeout):
            self.messageAvailable.emit(socket.readAll().data().decode('utf-8'))
            socket.disconnectFromServer()
        else:
            pass

    def isRunning(self):
        return self._isRunning

    def sendMessage(self, message):
        assert(self._isRunning)

        if self.isRunning():
            socket = QLocalSocket(self)
            socket.connectToServer(self._key, QIODevice.WriteOnly)
            if not socket.waitForConnected(self._timeout):
                return False
            socket.write(message.encode('utf-8'))
            if not socket.waitForBytesWritten(self._timeout):
                return False
            socket.disconnectFromServer()
            return True
        return False
