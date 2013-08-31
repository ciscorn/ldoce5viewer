# -*- coding: utf-8 -*-

'''Entry transformer

This module generates HTML documents from LDOCE's XML entry documents.
'''

from __future__ import absolute_import, unicode_literals

import re
import platform

try:
    from urllib.parse import urlencode
except:
    from urllib import urlencode

from lxml.etree import Element, tounicode

from .utils import shorten_id
from ..utils.compat import basestring

_SPAN_BUBBLEUP_HEAD = frozenset(('$', ';', ':', ',', '|', ', →', 'at'))
_SPAN_BUBBLEUP_TAIL = frozenset(('$', ';', ',', '|', ', →'))


def _E(tag, attrib={}, children=()):
    """Make an element"""

    elem = Element(tag, attrib)
    x = elem
    for c in children:
        if c is None:
            continue

        if isinstance(c, basestring):
            if x != elem:
                if x.tail:
                    x.tail += c
                else:
                    x.tail = c
            else:
                if x.text:
                    x.text += c
                else:
                    x.text = c
        else:
            elem.append(c)
            x = c

    return elem


def _preprocess_span(elem):
    '''make markups sane'''

    def is_plainspan(e):
        return (
            e.tag == 'span' and
            e.get('class', 'neutral') == 'neutral')

    for c in elem:
        _preprocess_span(c)

    if elem.text and len(elem) == 0:
        if elem.text.startswith(" "):
            elem.text = elem.text[1:]
            elem.addprevious(_E("span", {}, [" "]))
        if elem.text.endswith(" "):
            elem.text = elem.text[:-1]
            elem.addnext(_E("span", {}, [" "]))

    if elem.getparent() is None:
        return

    if elem.tag != 'Crossref':
        if len(elem) >= 1:
            span = elem[0]
            if elem.text is None and is_plainspan(span):
                elem.remove(span)
                if span.text is not None:
                    m = re.match(r'(\s*)(.*)', span.text)
                    group = m.group
                    if group(2).strip() in _SPAN_BUBBLEUP_HEAD:
                        elem.text = span.tail
                        span.tail = None
                    else:
                        span.text = group(1)
                        elem.text = group(2)
                        if span.tail:
                            elem.text += span.tail
                            span.tail = None
                    elem.addprevious(span)
                else:
                    elem.text = span.tail

        if len(elem) >= 1:
            span = elem[-1]
            if span.tail is None and is_plainspan(span):
                elem.remove(span)
                if span.text is not None:
                    m = re.match(r'(.*)(\s*)', span.text)
                    group = m.group
                    if group(1).strip() in _SPAN_BUBBLEUP_TAIL:
                        pass
                    else:
                        span.text = group(2)
                        if len(elem) >= 1:
                            last = elem[-1]
                            last.tail = (last.tail or '') + group(1)
                        else:
                            elem.text = (elem.text or '') + group(1)
                    elem.addnext(span)


def _as_span(elem, root):
    '''transform an element as <span>'''

    attrib = {'class': elem.tag.lower()}
    _id = elem.get('id')
    if _id is not None:
        attrib['id'] = shorten_id(_id)

    children = [elem.text]
    for c in elem:
        children.extend(_dispatch(c, root))
        children.append(c.tail)

    yield _E('span', attrib, children)


def _as_div(elem, root):
    '''transform an element as <div>'''

    attrib = {'class': elem.tag.lower()}
    _id = elem.get('id')
    if _id:
        attrib['id'] = shorten_id(_id)

    children = [elem.text]
    for c in elem:
        children.extend(_dispatch(c, root))
        children.append(c.tail)

    yield _E('div', attrib, children)


def _trans_sense(elem, root):
    attrib = {'class': elem.tag.lower()}
    if elem.find('span[@class="sensenum"]') is not None:
        attrib['class'] += ' sensewithnum'
    if elem.get('id', None) is not None:
        attrib['id'] = shorten_id(elem.get('id'))

    children = [elem.text]
    for c in elem:
        children.extend(_dispatch(c, root))
        children.append(c.tail)

    yield _E('div', attrib, children)


def _trans_ref(elem, root):
    topic = elem.get('topic')
    if len(topic.split('.')) == 4:
        id23 = shorten_id(topic)
        href = '/fs/' + id23
        if elem.get('bookmark', None) is not None:
            href += '#' + shorten_id(elem.get('bookmark'))
    else:
        href = './' + elem.get('topic')

    text = elem.text

    suffix = elem.find('SUFFIX')
    if suffix is not None:
        text += suffix.text

    children = [text]
    for c in elem:
        children.extend(_dispatch(c, root))
        children.append(c.tail)

    yield _E('a', {'href': href, 'class': 'ref'}, children)


def _trans_nondv(elem, root):
    refhwd = elem.find('REFHWD')
    href = '#'
    text = ''
    if refhwd is not None:
        text = refhwd.text
        href = 'lookup:///?' + urlencode({'q': text.strip().encode('utf-8')})

    suffix = elem.find('SUFFIX')
    if suffix is not None:
        text += suffix.text

    yield _E('a', {'href': href, 'class': 'nondv'}, [text])


def _trans_assets(root):
    colloc = []
    thesaurus = []
    example = []
    phrase = []
    word = []
    external = []

    assets = {}
    for asset in root.iterfind('.//EntryAsset'):
        asset_type = asset.get('type').lower()
        assets[asset_type] = '_'.join(
            ref.get('topic') for ref in asset.iterfind('Refs/Ref'))

    if 'entry_collocations' in assets:
        colloc.append(('This Entry',
                       '/collocations/' + assets['entry_collocations']))
    if 'other_entries_collocations' in assets:
        colloc.append(
                ('Other Entries',
                 '/collocations/' + assets['other_entries_collocations']))
    if 'corpus_collocations' in assets:
        colloc.append(('Corpus',
                       '/collocations/' + assets['corpus_collocations']))
    if 'thesaurus' in assets:
        thesaurus.append(('Thesaurus',
                          '/thesaurus/' + assets['thesaurus']))
    if 'activator' in assets:
        thesaurus.append(('Activator',
            '/thesaurus/' + assets['activator']))
    if 'word_sets' in assets:
        thesaurus.append(('Word Set',
            '/word_sets/' + assets['word_sets']))
    if 'other_dictionary_examples' in assets:
        example.append(('Other Dicts',
            '/examples/' + assets['other_dictionary_examples']))
    if 'corpus_examples' in assets:
        example.append(('Corpus',
            '/examples/' + assets['corpus_examples']))
    if 'entry_phrases' in assets:
        phrase.append(('This Entry',
            '/phrases/' + assets['entry_phrases']))
    if 'other_entries_phrases' in assets:
        phrase.append(('Other Entries',
            '/phrases/' + assets['other_entries_phrases']))
    if 'word_families' in assets:
        word.append(('Family',
            '/word_families/' + assets['word_families']))
    if 'etymology' in assets:
        word.append(('Origin',
            '/etymologies/' + assets['etymology']))

    is_noun = False
    pos_elems = root.findall('Head/POS')
    if not len(pos_elems):
        is_noun = True
    else:
        for e in pos_elems:
            if ''.join(e.itertext()).strip() == 'noun':
                is_noun = True

    if is_noun:
        hwd = root.find('Head/HWD/BASE')
        external.append(('Wikipedia',
            'http://en.wikipedia.org/w/index.php?' +
                urlencode(dict(search=hwd.text.encode('utf-8')))))
        external.append(('Google Images',
            'http://www.google.com/images?' +
                urlencode(dict(hl='en', q=hwd.text.encode('utf-8')))))

    def make_box(title, classname, items):
        head = _E('div', {'class': 'assethead'}, [title])
        c = []
        for (name, link) in items:
            c.append(_E('li', {}, (_E('a', dict(href=link), name), )))

        body = _E('ul', {'class': 'assetbody'}, c)
        yield _E('div', {'class': 'assetbox ' + classname}, (head, body))

    r = []
    if word:
        r.extend(make_box('Word', 'assets-word', word))
    if colloc:
        r.extend(make_box('Collocations', 'assets-collo', colloc))
    if thesaurus:
        r.extend(make_box('Thesaurus', 'assets-thes', thesaurus))
    if phrase:
        r.extend(make_box('Phrase Bank', 'assets-phr', phrase))
    if example:
        r.extend(make_box('Example Bank', 'assets-exas', example))
    if external:
        r.extend(make_box('Web', 'assets-link', external))

    return _E('div', {'class': 'assets'}, r)


def _trans_span(elem, root):
    attrib = elem.attrib
    text = elem.text
    attr_class = attrib.get('class')
    if attr_class:
        if attr_class == 'exabullet':
            return
        elif attr_class == 'sensenum':
            yield _E('span', attrib, (text, ' '))
        elif attr_class == 'heading':
            yield _E('div', attrib, (text, ))
        else:
            yield _E('span', attrib, (text, ))
    elif text is not None:
        yield text
    else:
        return


def _trans_br(elem, root):
    yield _E('br')


def _trans_audio(elem, root):
    topic = elem.get('topic')
    res = elem.get('resource').lower()
    path = 'audio:///{0}/{1}'.format(res, topic.split('/')[-1])
    attrib = { 'href': path, 'class': 'audio' }
    if res == 'exa_pron' or res == 'sfx':
        attrib['title'] = 'Play'
        img = 'static:///images/speaker_eg.png'
    elif res == 'gb_hwd_pron':
        attrib['title'] = 'British'
        img = 'static:///images/speaker_br.png'
    elif res == 'us_hwd_pron':
        attrib['title'] = 'American'
        img = 'static:///images/speaker_am.png'
    else:
        attrib['title'] = 'Not Supported'
        img = 'static:///images/speaker_eg.png'

    children = (_E('img', {'src': img}), )
    yield _E('a', attrib, children)


def _trans_illustration(elem, root):
    topic = elem.get('thumb')
    filename = topic.split('/')[-1]
    path_thumb = '/picture/thumbnail/' + filename
    path_full = '/picture/fullsize/' + filename
    attrib = {'src': path_thumb, 'style': 'float: right'}
    children = (_E('img', attrib), )
    yield _E('a', {'class': 'illust', 'href': path_full}, children)


def _trans_skip(elem, root):
    return ()


def _trans_hwd(elem, root):
    if root.find('Head/HYPHENATION') is None:
        hwd = elem
        if hwd is not None:
            yield _E('span', {'class': 'hwd'}, [hwd.text])
    return


_TRANS_MAP = {
        'ACTIV': _trans_skip,
        'Audio': _trans_audio,
        'br': _trans_br,
        'ColloBox': _as_div,
        'Collocate': _as_div,
        'ColloExa': _as_div,
        'Crossref': _as_div,
        'Head': _as_div,
        'Deriv': _as_div,
        'Entry': _as_div,
        'EXAMPLE': _as_div,
        'EXPL': _as_span,
        'Exponent': _as_div,
        'F2NBox': _as_div,
        'GramBox': _as_div,
        'GramExa': _as_div,
        'Hint': _as_div,
        'HWD': _trans_hwd,
        'ILLUSTRATION': _trans_illustration,
        'INFLX': _trans_skip,
        'PhrVbEntry': _as_div,
        'NonDV': _trans_nondv,
        'Ref': _trans_ref,
        'RunOn': _as_div,
        'SECHEADING': _as_div,
        'Section': _as_div,
        'SE_EntryAssets': _trans_skip,
        'Sense': _trans_sense,
        'span': _trans_span,
        'SpokenSect': _as_div,
        'Subsense': _trans_sense,
        'Tail': _as_div,
        'ThesBox': _as_div,
        }


def _dispatch(elem, root):
    '''invoke a proper transformation function for a given element'''
    f = _TRANS_MAP.get(elem.tag, _as_span)
    return f(elem, root)


def body2html(root):
    _preprocess_span(root)
    r = []

    # pass the root element to the dispatcher
    for el in _dispatch(root, root):
        if not isinstance(el, basestring):
            r.append(tounicode(el, pretty_print=True, method='html'))

    # replace some characters
    body = ''.join(r).translate({0x2027: 0xb7})
    body = re.sub(r'([→►↔])', r'<span>\1</span>', body)
    if platform.release() == 'XP' and platform.system() == 'Windows':
        body = re.sub(r'([\u02cc\u02c8\u2194])',
                r'<span class="winxpsym">\1</span>', body)

    return body

