'''Advanced Search'''

from __future__ import absolute_import
from __future__ import unicode_literals

from operator import itemgetter

from PyQt5.QtCore import Qt, QUrl, QUrlQuery
from PyQt5.QtGui import (
    QKeySequence, QIcon)
from PyQt5.QtWidgets import (
    QAction, QDialog, QTreeWidgetItem,)

from ..ldoce5 import advtree
from ..utils.compat import range
from ..utils.text import MATCH_OPEN_TAG, MATCH_CLOSE_TAG

from .ui.advanced import Ui_Dialog
from .config import get_config


class AdvancedSearchDialog(QDialog):
    '''The 'Advanced Search' dialog'''
    def __init__(self, mainwindow):
        QDialog.__init__(self, mainwindow, Qt.Tool)

        self._mainwindow = mainwindow

        self._ui = ui = Ui_Dialog()
        ui.setupUi(self)

        ui.actionFocusLineEdit = QAction(self)
        self.addAction(ui.actionFocusLineEdit)
        ui.actionFocusLineEdit.setShortcut(QKeySequence('Ctrl+L'))
        ui.actionFocusLineEdit.triggered.connect(self.setFocusOnPhraseBox)

        ui.treeWidget.itemChanged.connect(self.__onTreeItemChanged)
        ui.lineEditPhrase.textChanged.connect(self._update_buttons)
        ui.buttonReset.clicked.connect(self.__onReset)
        ui.buttonSearch.clicked.connect(self.__onSearch)
        ui.buttonReset.setDisabled(True)
        self._tree_checked = False

        ui.buttonSearch.setIcon(QIcon(':/icons/edit-find.png'))

        try:
            if 'advancedDialogGeometry' in get_config():
                self.restoreGeometry(get_config()['advancedDialogGeometry'])
        except:
            pass

        self._update_buttons()

        self._load_tree()

    def closeEvent(self, event):
        try:
            get_config()['advancedDialogGeometry'] = bytes(self.saveGeometry())
        except:
            pass

    def _make_filter(self):
        tw = self._ui.treeWidget

        def scan(item, or_set):
            node = item.data(0, Qt.UserRole)
            if 'code' in node:
                if item.checkState(0) == Qt.Checked:
                    or_set.add('asfilter:' + node['code'])
            for i in range(item.childCount()):
                child = item.child(i)
                scan(child, or_set)

        andlist = []
        for i in range(tw.topLevelItemCount()):
            item = tw.topLevelItem(i)
            or_set = set()
            scan(item, or_set)
            if or_set:
                andlist.append('(' + ' OR '.join(or_set) + ')')
        return ' AND '.join(andlist)

    def __onSearch(self):
        query_str = self._ui.lineEditPhrase.text().strip()
        asfilters = self._make_filter()
        self._mainwindow.fullSearch(query_str, asfilters, mode='headwords')

    def __onReset(self):
        self._ui.lineEditPhrase.clear()
        tw = self._ui.treeWidget
        for i in range(tw.topLevelItemCount()):
            item = tw.topLevelItem(i)
            item.setCheckState(0, Qt.Unchecked)
            tw.collapseItem(item)

    def _load_tree(self):
        data = advtree.load()

        def add_children(child_nodes, parent):
            children = []
            for node in child_nodes:
                twitem = QTreeWidgetItem((node['label'], ))
                twitem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                twitem.setCheckState(0, Qt.Unchecked)
                twitem.setData(0, Qt.UserRole, node)
                if 'children' in node:
                    add_children(node['children'], twitem)
                children.append(twitem)

            parent.addChildren(children)

        for topnode in data:
            twitem = QTreeWidgetItem((topnode['label'], ))
            twitem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            twitem.setCheckState(0, Qt.Unchecked)
            twitem.setData(0, Qt.UserRole, topnode)
            if 'children' in topnode:
                add_children(topnode['children'], twitem)
            self._ui.treeWidget.addTopLevelItem(twitem)

    def __onTreeItemChanged(self, item, column):
        if column != 0:
            return
        tw = self._ui.treeWidget

        node = item.data(0, Qt.UserRole)
        check_state = item.checkState(0)

        if ('code' not in node) and (check_state == Qt.Checked):
            children_checked = False
            for i in range(item.childCount()):
                child = item.child(i)
                if child.checkState(0) != Qt.Unchecked:
                    children_checked = True
                    break
            if not children_checked:
                tw.expandItem(item)
            item.setCheckState(0, Qt.Unchecked)

        parent = item.parent()
        if parent:
            parent_state = parent.checkState(0)
            children_checked = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.checkState(0) != Qt.Unchecked:
                    children_checked = True
                    break
            if children_checked and parent_state == Qt.Unchecked:
                parent.setCheckState(0, Qt.PartiallyChecked)
            elif not children_checked and parent_state == Qt.PartiallyChecked:
                parent.setCheckState(0, Qt.Unchecked)

        if check_state == Qt.Unchecked and 'children' in node:
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, Qt.Unchecked)

        checked = False
        for i in range(tw.topLevelItemCount()):
            item = tw.topLevelItem(i)
            if item.checkState(0) != Qt.Unchecked:
                checked = True
                break
        self._tree_checked = checked
        self._update_buttons()

    def _update_buttons(self):
        query_str = self._ui.lineEditPhrase.text().strip()
        self._ui.buttonSearch.setEnabled(bool(query_str or self._tree_checked))
        self._ui.buttonReset.setEnabled(bool(query_str or self._tree_checked))

    def setFocusOnPhraseBox(self):
        self._ui.lineEditPhrase.setFocus()
        self._ui.lineEditPhrase.selectAll()


ADV_HEADER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="static:///styles/search.css">
<script src="static:///scripts/jquery.js"></script>
<script src="static:///scripts/search.js"></script>
</head>
<body>"""


def _render_header(title, mode, phrase, filters):
    r = []
    r.append(ADV_HEADER)
    r.append('<h1>{0}</h1>'.format(title))
    r.append('<ul class="nav">\n')

    modes = [(name, spec) for (name, spec) in MODE_DICT.items()]
    modes.sort(key=itemgetter(0))

    for (name, spec) in modes:
        href = QUrl('search:///')
        urlquery = QUrlQuery()
        if phrase:
            urlquery.addQueryItem('phrase', phrase)
        if filters:
            urlquery.addQueryItem('filters', filters)
        urlquery.addQueryItem('mode', name)
        href.setQuery(urlquery)
        if name != mode:
            r.append(
                '<li><a href="{href}">{title}</a></li>\n'.format(
                    href=href.toEncoded(), title=spec['title']))
        else:
            r.append(
                '<li><span class="sel">{title}<span></li>\n'.format(
                    href=href.toEncoded(), title=spec['title']))

    r.append('</ul>\n')

    return ''.join(r)


def _render_footer():
    return '</head></body>'


def _replace_tags(s):
    s = MATCH_OPEN_TAG.sub(r'<span class="label_\1">', s)
    return MATCH_CLOSE_TAG.sub('</span>', s)


def _render_defexa(items, mode):
    r = []

    if not items:
        r.append('<p class="no">No Items Found</p>\n')
    else:
        r.append('<ul class="result r_{0}">\n'.format(mode))
        for item in items:
            (label, path, sortkey, prio, text) = item
            r.append('<li>'
                     '<a href="dict://{path}">'
                     '<span class="entry">{label}</span>'
                     ' <span class="text">{text}</span>'
                     '</a>'
                     '</li>\n'.format(
                         item=item,
                         label=_replace_tags(label),
                         path=path,
                         text=text,
                     ))
        r.append('</ul>\n')

    return ''.join(r)


def _render_hwdphr(items, mode):
    r = []
    if not items:
        r.append('<p class="no">No Items Found</p>\n')
    else:
        r.append('<ul class="excmd">\n')
        if mode in ('headwords', 'phrasalverbs'):
            r.append(
                '''<li><a href="#" onclick="$('.label_p').hide();'''
                '''$('.label_s').hide(); $(this).hide();">'''
                '''Hide extra information</a></li>''')
        r.append('</ul>\n')

        r.append('<ul class="result r_{0}">\n'.format(mode))
        for item in items:
            (label, path, sortkey, prio, text) = item
            r.append('<li>'
                     '<a href="dict://{path}">{label}</a>'
                     '</li>\n'.format(
                         item=item,
                         label=_replace_tags(label),
                         path=path
                     ))
        r.append('</ul>\n')

    return ''.join(r)


def search_and_render(url, fulltext_hp, fulltext_de):
    query = QUrlQuery(url)
    mode = query.queryItemValue('mode')
    phrase = query.queryItemValue('phrase')
    filters = query.queryItemValue('filters')

    r = []
    if mode in MODE_DICT:
        spec = MODE_DICT[mode]
        searcher = fulltext_hp if (spec['searcher'] == 'hp') else fulltext_de
        collector = searcher.make_collector(spec['limit'])
        res = searcher.search(
            collector,
            query_str1=phrase, query_str2=filters,
            itemtypes=spec['itemtypes'],
            highlight=spec['highlight'])
        r.append(_render_header(spec['title'], mode, phrase, filters))
        r.append(spec['renderer'](res, mode))
        r.append(_render_footer())
    else:
        r.append(_render_header('Advanced Search', mode, phrase, filters))
        r.append(_render_footer())

    return ''.join(r)


MODE_DICT = {
    'headwords': dict(
        title='Headwords', itemtypes=('hm', ), searcher='hp',
        wildcard=True,
        limit=None, highlight=False, renderer=_render_hwdphr, prio=1),
    'phrasalverbs': dict(
        title='Phrasal Verbs', itemtypes=('hp', ), searcher='hp',
        wildcard=False,
        limit=None, highlight=False, renderer=_render_hwdphr, prio=2),
    'phrases': dict(
        title='Phrases', itemtypes=('pl', ), searcher='hp',
        wildcard=False,
        limit=3000, highlight=False, renderer=_render_hwdphr, prio=3),
    'collocations': dict(
        title='Collocations', itemtypes=('p', ), searcher='hp',
        wildcard=False,
        limit=3000, highlight=False, renderer=_render_hwdphr, prio=4),
    'examples': dict(
        title='Examples', itemtypes=('e', ), searcher='de',
        wildcard=False,
        limit=3000, highlight=True, renderer=_render_defexa, prio=5),
    'definitions': dict(
        title='Definitions', itemtypes=('d', ), searcher='de',
        wildcard=False,
        limit=3000, highlight=True, renderer=_render_defexa, prio=6),
}
