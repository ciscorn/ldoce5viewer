import sys

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import *
from PySide6.QtWidgets import *

from ...utils.text import ellipsis

DisplayRole = Qt.ItemDataRole.DisplayRole
State_Selected = QStyle.StateFlag.State_Selected


INDEX_SELECTED_COLOR = QColor(228, 228, 228)


class ToolButton(QToolButton):
    """QToolButton without menu-arrow"""

    def paintEvent(self, event):
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        opt.features &= ~QStyleOptionToolButton.ToolButtonFeature.HasMenu
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)

    def sizeHint(self):
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        opt.features &= ~QStyleOptionToolButton.ToolButtonFeature.HasMenu
        content_size = opt.iconSize
        return self.style().sizeFromContents(
            QStyle.ContentsType.CT_ToolButton, opt, content_size, self
        )


class LineEdit(QLineEdit):
    """QLineEdit with a clear button"""

    _ICONSIZE = 16

    def __init__(self, parent=None):
        super(LineEdit, self).__init__(parent)
        ICONSIZE = self._ICONSIZE

        self._buttonFind = QToolButton(self)
        self._buttonFind.setCursor(Qt.CursorShape.ArrowCursor)
        self._buttonFind.setIconSize(QSize(ICONSIZE, ICONSIZE))
        self._buttonFind.setIcon(QIcon(":/icons/edit-find.png"))
        self._buttonFind.setStyleSheet(
            "QToolButton { border: none; margin: 0; padding: 0; }"
        )
        self._buttonFind.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonFind.clicked.connect(self.selectAll)

        self._buttonClear = QToolButton(self)
        self._buttonClear.hide()
        self._buttonClear.setToolTip("Clear")
        self._buttonClear.setCursor(Qt.CursorShape.ArrowCursor)
        self._buttonClear.setIconSize(QSize(ICONSIZE, ICONSIZE))
        self._buttonClear.setIcon(QIcon(":/icons/edit-clear.png"))
        self._buttonClear.setStyleSheet(
            "QToolButton { border: none; margin: 0; padding: 0; }"
        )
        self._buttonClear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonClear.clicked.connect(self.clear)

        minsize = self.minimumSizeHint()
        framewidth = self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
        margin = self.textMargins()
        margin.setLeft(3 + ICONSIZE + 1)
        margin.setRight(1 + ICONSIZE + 3)
        self.setTextMargins(margin)

        height = max(minsize.height(), ICONSIZE + (framewidth + 2) * 2)
        self.setMinimumSize(
            max(minsize.width(), (ICONSIZE + framewidth + 2 + 2) * 2),
            int(height / 2.0 + 0.5) * 2,
        )

        self.textChanged.connect(self.__onTextChanged)

    def resizeEvent(self, event):
        ICONSIZE = self._ICONSIZE
        framewidth = self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
        rect = self.rect()
        self._buttonFind.move(framewidth + 3 - 1, (rect.height() - ICONSIZE) / 2 - 1)
        self._buttonClear.move(
            rect.width() - framewidth - 3 - ICONSIZE - 1,
            (rect.height() - ICONSIZE) / 2 - 1,
        )

    def __onTextChanged(self, text):
        self._buttonClear.setVisible(bool(text))


class LineEditFind(QLineEdit):
    shiftReturnPressed = Signal()
    escapePressed = Signal()

    def __init__(self, parent):
        super(LineEditFind, self).__init__(parent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            self.shiftReturnPressed.emit()
        elif event.key() == Qt.Key.Key_Return:
            self.returnPressed.emit()
        else:
            super(LineEditFind, self).keyPressEvent(event)


class HtmlListWidget(QListWidget):
    class HtmlItemDelegate(QStyledItemDelegate):

        MARGIN_H = 5
        if sys.platform.startswith("win"):
            MARGIN_V = 3
        elif sys.platform.startswith("darwin"):
            MARGIN_V = 4
        else:
            MARGIN_V = 5

        def __init__(self, parent=None):
            super(HtmlListWidget.HtmlItemDelegate, self).__init__(parent)
            self._doc = QTextDocument()
            self._doc.setDocumentMargin(0)
            self._item_size = None

        def paint(self, painter, option, index):
            doc = self._doc
            painter.resetTransform()
            rect = option.rect
            if option.state & State_Selected:
                painter.fillRect(rect, INDEX_SELECTED_COLOR)
            doc.setHtml(index.data(DisplayRole))
            px = rect.x() + self.MARGIN_H
            py = rect.y() + self.MARGIN_V
            painter.translate(px, py)
            doc.drawContents(painter)

        def sizeHint(self, option, index):
            s = self._item_size
            if not s:
                doc = self._doc
                doc.setDefaultFont(option.font)
                doc.setHtml('<body>MNmn012<span class="p">012</span></body>')
                height = doc.size().height() + self.MARGIN_V * 2
                s = self._item_size = QSize(0, height)
            return s

        def setStyleSheet(self, s):
            self._doc.setDefaultStyleSheet(s)
            self._item_size = None

    def __init__(self, parent):
        super(HtmlListWidget, self).__init__(parent)
        QListWidget.setStyleSheet(self, "QListWidget{background-color: white;}")
        self._item_delegate = HtmlListWidget.HtmlItemDelegate(parent)
        self.setItemDelegate(self._item_delegate)

    def keyPressEvent(self, event):
        event.ignore()

    def setStyleSheet(self, s):
        self._item_delegate.setStyleSheet(s)


class WebView(QWebEngineView):
    wheelWithCtrl = Signal(int)

    def __init__(self, parent):
        super(WebView, self).__init__(parent)

        self.setStyleSheet("QWebEngineView{background-color: white;}")

        self._actionSearchText = QAction(self)
        if sys.platform != "darwin":
            self._actionSearchText.setIcon(
                QIcon.fromTheme("edit-find", QIcon(":/icons/edit-find.png"))
            )
        self._actionCopyPlain = QAction(self)
        self._actionCopyPlain.setText("Copy")
        if sys.platform != "darwin":
            self._actionCopyPlain.setIcon(
                QIcon.fromTheme("edit-copy", QIcon(":/icons/edit-copy.png"))
            )
        self._actionCopyPlain.triggered.connect(self._copyAsPlainText)
        self._actionCopyPlain.setShortcut(QKeySequence.StandardKey.Copy)
        self.page().selectionChanged.connect(self.__onSelectionChanged)
        self.__onSelectionChanged()
        self._actionDownloadAudio = QAction(u"Download mp3", self)

    def _copyAsPlainText(self):
        text = self.selectedText().strip()
        QApplication.clipboard().setText(text)

    @property
    def actionSearchText(self):
        return self._actionSearchText

    @property
    def actionCopyPlain(self):
        return self._actionCopyPlain

    @property
    def actionDownloadAudio(self):
        return self._actionDownloadAudio

    @property
    def audioUrlToDownload(self):
        return self._audioUrlToDownload

    def __onSelectionChanged(self):
        text = self.selectedText()
        self._actionCopyPlain.setEnabled(bool(text))

    def contextMenuEvent(self, event):
        page = self.page()
        menu = self.createStandardContextMenu()
        actions = menu.actions()

        # inserts the "Download audio" action
        # FIXME
        # frame = page.frameAt(event.pos())
        # hit_test_result = frame.hitTestContent(event.pos())
        # if hit_test_result.linkUrl().scheme() == "audio":
        #     self._audioUrlToDownload = hit_test_result.linkUrl()
        #     menu.insertAction(actions[0] if actions else None, self.actionDownloadAudio)

        # Insert the "Search for ..." action
        text = page.selectedText().strip().lower()
        if text:
            text = ellipsis(text, 18)
            self._actionSearchText.setText(u'Lookup "{0}"'.format(text))
            menu.insertAction(actions[0] if actions else None, self.actionSearchText)

        # Replace WebKit's copy action with plain-text copying
        try:
            action_copy = page.action(QWebEnginePage.WebAction.Copy)
            if action_copy in actions:
                menu.insertAction(action_copy, self.actionCopyPlain)
                menu.removeAction(action_copy)
        except:
            pass

        # Inserts a separator before "Inspect Element"
        # try:
        #     action_inspector = page.action(QWebEnginePage.InspectElement)
        #     pos = actions.index(action_inspector)
        # except:
        #     pass
        # else:
        #     if pos > 0 and not actions[pos - 1].isSeparator():
        #         menu.insertSeparator(action_inspector)

        # display the context menu
        menu.exec_(event.globalPos())

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            pass
        else:
            super(WebView, self).keyPressEvent(event)

    # --------------
    # Mouse Events
    # --------------

    def mousePressEvent(self, event):
        if sys.platform not in ("win32", "darwin"):
            if self.handleNavMouseButtons(event):
                return
        super(WebView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if sys.platform in ("win32", "darwin"):
            if self.handleNavMouseButtons(event):
                return
        super(WebView, self).mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.wheelWithCtrl.emit(event.angleDelta().y())
            return
        super(WebView, self).wheelEvent(event)

    def handleNavMouseButtons(self, event):
        if event.button() == Qt.MouseButton.XButton1:
            self.triggerPageAction(QWebEnginePage.WebAction.Back)
            return True
        elif event.button() == Qt.MouseButton.XButton2:
            self.triggerPageAction(QWebEnginePage.WebAction.Forward)
            return True
        return False
