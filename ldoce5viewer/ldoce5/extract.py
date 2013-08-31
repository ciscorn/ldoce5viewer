# -*- coding: utf-8 -*-

'''Searchable item extractor'''

from __future__ import absolute_import
from __future__ import unicode_literals

import re
from cgi import escape
from itertools import chain

import lxml.etree as et

from .utils import shorten_id
from ..utils.compat import range


_MATCH_SPACE = re.compile('\s+')
_EXCLUDE_TAGS = frozenset(('span', 'OBJECT', 'GLOSS'))
_SEARCH_COUNTABLE = re.compile(
    r"(\bcountable\b|\bc\b|\b(often|usually)\s+plural\b)")
_SEARCH_UNCOUNTABLE = re.compile(r"(\buncountable\b)")


"""
typecode:
    hm:  headword
    hv:  headword - variant
    hp:  headword - phrasalverb
    p:   phrase
    pl:  phrase - lexunit
    ac:  activator - concept
    ae:  activator - exponent

    d:   definition
    e:   example
"""


def _get_text(elem):
    s = []

    def rec(e):
        if e.tag in _EXCLUDE_TAGS:
            return
        if e.text is not None:
            s.append(e.text)
        for c in e:
            rec(c)
            if c.tail is not None:
                s.append(c.tail)
    rec(elem)
    return ''.join(s).strip()


def _get_text2(elem):
    s = []
    text = elem.text
    if text is not None:
        s.append(text)
    for c in elem:
        if c.tag == 'COLLOINEXA':
            s.append(_get_text(c))
        tail = c.tail
        if tail is not None:
            s.append(tail)
    return _MATCH_SPACE.sub(' ', ' '.join(s)).strip()


def _remove_article(s):
    if s.startswith('a '):
        return s[2:]
    elif s.startswith('an '):
        return s[3:]
    else:
        return s


def _make_variations(base, inflections):
    if len(base.split()) > 1:
        return {}

    v = set()
    v.add(base.lower())
    v.update(inflx.lower() for inflx in inflections)
    if len(v) <= 1:
        return {base: []}

    v = tuple(v)
    ret = {}
    for i in range(len(v)):
        ret[v[i]] = v[:i] + v[i+1:]
    return ret


def _get_incorrect_inflections(
        base, pos_elems, gram_main_elems, gram_sub_elems, num_syllable):

    poslist = frozenset(_get_text(e).lower() for e in pos_elems)
    gramlist_main = frozenset(_get_text(e).lower() for e in gram_main_elems)
    gramlist_sub = frozenset(_get_text(e).lower() for e in gram_sub_elems)
    gramlist = gramlist_main | gramlist_sub

    def handle_noun():
        for s in gramlist:
            if _SEARCH_COUNTABLE.search(s):
                return ()

        endswith = base.endswith
        if endswith('y'):
            return (base + 's', base[:-1] + 'ies', )
        elif endswith('f'):
            return (base[:-1] + 'ves', )
        elif endswith('fe'):
            return (base[:-2] + 'ves', )
        else:
            return (base + 's', base + 'es')

    def handle_adjective():
        endswith = base.endswith

        def make_comparative():
            if base.endswith('e'):
                return (base + 'r', base + 'st')
            elif base.endswith('y'):
                s = base[:-1]
                return (s + 'ier', s + 'iest')
            else:
                return (base + 'er', base + 'est')
            return ()

        for s in gramlist:
            if "no comparative" in s:
                return make_comparative()

        if num_syllable >= 3:
            return make_comparative()
        elif num_syllable >= 2 and not (
                endswith('y') or endswith('le') or endswith('er')):
            return make_comparative()

        return ()

    r = []
    for pos in poslist:
        if pos == 'noun':
            r.extend(handle_noun())
        elif pos == 'adjective':
            r.extend(handle_adjective())

    return r


def get_entry_items(entry_data):

    root = et.fromstring(entry_data)
    root_id = shorten_id(root.get('id'))
    head = root.find('Head')
    hyphenation = head.find('HYPHENATION')
    num_syllable = 1
    if hyphenation is not None:
        num_syllable = _get_text(hyphenation).count("‧") + 1
    is_freq = (head.find('FREQ') is not None)
    hwdplain = _get_text(head.find('HWD/BASE'))

    gram_main_elems = head.findall('.//GRAM')

    pos_elems = head.findall('.//POS')
    poslist = frozenset(_get_text(e).lower() for e in pos_elems)

    incorrect = frozenset(_get_incorrect_inflections(
        hwdplain,
        pos_elems,
        gram_main_elems,
        root.findall('Sense//GRAM'),
        num_syllable))

    gramlist_main = frozenset(_get_text(e).lower() for e in gram_main_elems)

    is_hwd_noun = 'noun' in poslist
    is_hwd_adj = 'adjective' in poslist

    if is_hwd_noun:
        is_uncountable = False
        for s in gramlist_main:
            unco = _SEARCH_UNCOUNTABLE.search(s)
            co = _SEARCH_COUNTABLE.search(s)
            if unco and not co:
                is_uncountable = True
    else:
        is_uncountable = False

    is_american = False
    is_british = False
    if head.find('AmEVariant') is None and head.find('BrEVariant') is None:
        for s in (_get_text(e) for e in head.iterfind('GEO')):
            if 'British' in s:
                is_british = True
            elif 'American' in s:
                is_american = True

    def _get_filter(elem, poslist=None):
        if elem.get('as_filter', None) is None:
            return ''

        z = set(elem.get('as_filter').replace('|', '').split())

        # some adjectives are mislabeled as adjective+nouns.
        if (poslist is None) and (not is_hwd_adj):
            z.discard('334')  # 334 -> adjective
        elif poslist and ('adjective' not in poslist):
            z.discard('334')  # 334 -> adjective

        return ' '.join(z)

    def make_hwd_label():
        hwd = head.find('HWD')
        baselabel = escape(_get_text(hwd.find('BASE')))

        homnum = head.find('HOMNUM')
        if homnum is not None:
            baselabel += '<s>{0}</s>'.format(escape(_get_text(homnum)))

        if is_freq:
            hwdlabel = '<f>{0}</f>'.format(baselabel)
        else:
            hwdlabel = '<n>{0}</n>'.format(baselabel)

        poslist = head.findall('POS')
        if poslist:
            hwdlabel += ' <p>{0}</p>'.format(
                escape(', '.join(_get_text(pos) for pos in poslist)))

        return hwdlabel

    hwdlabel = make_hwd_label()

    def get_hwd():
        path = '/fs/' + root_id
        hwd = head.find('HWD')
        hwdplain = _get_text(hwd.find('BASE'))
        asfilter = _get_filter(hwd)

        if is_uncountable:
            asfilter += ' u1'

        if is_british:
            asfilter += ' u2'

        if is_american:
            asfilter += ' u3'

        label = '<h>{0}</h>'.format(hwdlabel)

        return ('hm', label, path, hwdplain, hwdplain, asfilter, 1)

    def get_hwd_variants():
        path = '/fs/' + root_id
        hwd = head.find('HWD')
        hwdplain = _get_text(hwd.find('BASE'))
        asfilter = _get_filter(hwd)

        for inflx in hwd.iterfind('INFLX'):
            inflxplain = _get_text(inflx)
            if inflxplain == hwdplain:
                continue
            if inflxplain in incorrect:
                continue
            inflxlabel = '<h><v>{0}</v> &rarr; {1}</h>'.format(
                escape(inflxplain), hwdlabel)
            yield ('hv', inflxlabel, path, inflxplain,
                   inflxplain, asfilter, 2)

        variants = chain(
            head.iterfind('.//LEXVAR'),
            head.iterfind('.//ORTHVAR'))

        for lexvar in variants:
            v_asfilter = _get_filter(lexvar)
            if lexvar.get('id', None) is None:
                continue
            v_id = lexvar.get('id')
            v_path = path + '#' + shorten_id(v_id)
            v_plains = tuple(set(
                _get_text(e) for e in lexvar.iterfind('INFLX')))
            for v_plain in v_plains:
                if v_plain in incorrect:
                    continue
                v_label = '<h><v>{0}</v> &rarr; {1}</h>'.format(
                    escape(v_plain), hwdlabel)
                yield ('hv', v_label, v_path, v_plain, v_plain, v_asfilter, 2)

        for abbr in head.iterfind('.//ABBR'):
            v_asfilter = ''
            v_plain = _get_text(abbr)
            v_label = '<h><v>{0}</v> &rarr; {1}</h>'.format(
                escape(v_plain), hwdlabel)
            yield ('hv', v_label, path, v_plain, v_plain, v_asfilter, 2)

    def get_phrvb(phrvb):
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(phrvb.get('id')))
        phrvbhwd = phrvb.find('Head/PHRVBHWD')
        plain = _get_text(phrvbhwd)
        asfilter = _get_filter(phrvbhwd)
        label = '<h><pv>{0}</pv> <p>phrasal verb</p></h>'.format(
            escape(plain))
        yield ('hp', label, path, plain, plain, asfilter, 1)

    def get_runon(runon):
        deriv = runon.find('DERIV')
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(deriv.get('id')))
        poslist = frozenset(_get_text(e).lower()
                            for e in runon.iterfind('.//POS'))
        asfilter = _get_filter(deriv, poslist)
        hwd = deriv.find('BASE')
        plain = _get_text(hwd)
        plain = plain.replace('\u02c8', '')
        plain = plain.replace('\u02cc', '')
        if poslist is not None:
            label = '<n>{0}</n> <p>{1}</p>'.format(
                    escape(plain), escape(', '.join(poslist)))
        else:
            label = '<n>{0}</n>'.format(escape(plain))
        yield ('hm', '<h>' + label + '</h>', path, plain, plain, asfilter, 1)

        incorrect = frozenset(_get_incorrect_inflections(
            plain,
            runon.findall('POS'),
            runon.findall('GRAM'),
            (),
            num_syllable))

        for inflx in deriv.iterfind('INFLX'):
            inflplain = _get_text(inflx)
            if inflplain == plain:
                continue
            if inflplain in incorrect:
                continue
            infllabel = '<h><v>{0}<v> &rarr; {1}</h>'.format(
                escape(inflplain), label)
            yield ('hv', infllabel, path, inflplain,
                   inflplain, asfilter, 1)

    def get_lexunit(elem):
        asfilter = _get_filter(elem)
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        plain = _get_text(elem)
        label = '<l><o>{0}</o> ({1})</l>'.format(escape(plain), hwdlabel)
        yield ('pl', label, path, plain, plain, asfilter, 9)

    def get_simple(elem):
        asfilter = _get_filter(elem)
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        plain = _get_text(elem)
        label = '<c><o>{0}</o> ({1})</c>'.format(plain, hwdlabel)
        yield ('p', label, path, plain, plain, asfilter, 10)

    def get_colloc(elem):
        asfilter = _get_filter(elem)
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        plain = _get_text(elem)
        plain = _remove_article(plain)
        label = '<c><o>{0}</o> ({1})</c>'.format(plain, hwdlabel)
        yield ('p', label, path, plain, plain, asfilter, 10)

    def get_collocate(elem):
        if elem.get('id', None) is None:
            return

        texts = chain(
            elem.iterfind('COLLOC'),
            elem.iterfind('.//LEXVAR'),
            elem.iterfind('.//ORTHVAR'))
        title = ', '.join(
            '<b>{0}</b>'.format(escape(_get_text(e))) for e in texts)

        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        for e in elem.iterfind('COLLEXA'):
            plain = _get_text2(e.find('BASE'))
            asfilter = _get_filter(e)
            label = "{0} &mdash; {1}".format(hwd_label, title)
            yield ('e', label, path, plain, hwd_plain, asfilter, 20)

        variants = chain(
            elem.iterfind('.//LEXVAR'),
            elem.iterfind('.//ORTHVAR'))
        for var in variants:
            if var.get('id', None) is None:
                continue
            path = '/fs/{0}#{1}'.format(
                root_id, shorten_id(var.get('id')))
            v_plain = _get_text(var)
            v_label = '<c><o>{0}</o> ({1})</c>'.format(v_plain, hwdlabel)
            yield ('p', v_label, path, v_plain, v_plain, '', 11)

    def get_exponent(elem):
        if elem.get('id', None) is None:
            return

        texts = chain(
            elem.iterfind('EXP'),
            elem.iterfind('.//LEXVAR'),
            elem.iterfind('.//ORTHVAR'))
        title = ', '.join(
            '<b>{0}</b>'.format(escape(_get_text(e))) for e in texts)

        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        for e in elem.iterfind('.//THESEXA'):
            asfilter = _get_filter(e)
            text = _get_text2(e.find('BASE'))
            yield ('e', hwd_label, path, text, hwd_plain, asfilter, 20)

        for d in elem.iterfind('.//DEF'):
            text = _get_text(d)
            asfilter = _get_filter(d)
            label = "{0} &mdash; {1}".format(hwd_label, title)
            yield ('d', label, path, text, hwd_plain, asfilter, 30)

    def get_example(elem):
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        asfilter = _get_filter(elem)
        text = _get_text2(elem.find('BASE'))
        yield ('e', hwd_label, path, text, hwd_plain, asfilter, 20)

        collo = tuple(_get_text(c) for c in elem.iterfind('.//COLLOINEXA'))
        if collo:
            coplain = ' '.join(collo)
            colabel = ' &hellip; '.join(escape(c) for c in collo)
            colabel = '<c><o>{0}</o> ({1})</c>'.format(colabel, hwdlabel)
            yield ('p', colabel, path, coplain, coplain, '', 15)

    def get_sense(elem):
        path = '/fs/{0}#{1}'.format(root_id, shorten_id(elem.get('id')))
        for d in elem.iterfind('.//DEF'):
            text = _get_text(d)
            asfilter = _get_filter(d)
            yield ('d', hwd_label, path, text, hwd_plain, asfilter, 30)

        variants = chain(
            elem.iterfind('.//LEXVAR'),
            elem.iterfind('.//ORTHVAR'))
        for var in variants:
            path = '/fs/{0}#{1}'.format(
                root_id, shorten_id(var.get('id')))
            v_plain = _get_text(var)\
                .replace("\xb7", "")\
                .replace("\u02c8", "")\
                .replace("\u02cc", "")
            v_label = '<l><o>{0}</o> ({1})</l>'.format(
                escape(v_plain), hwdlabel)
            yield ('pl', v_label, path, v_plain, v_plain, '', 11)

    def gen(f, elems):
        for e in elems:
            for r in f(e):
                yield r

    items = []
    headword = get_hwd()
    items.append(headword)
    hwd_label = headword[1]
    hwd_plain = headword[3]

    inflections = set()
    for v in get_hwd_variants():
        items.append(v)
        var_plain = v[3]
        inflections.add(var_plain)

    variations = _make_variations(hwd_plain, inflections)

    iterfind = root.iterfind
    for r in gen(get_sense, iterfind('.//Sense')):
        items.append(r)
    for r in gen(get_runon, iterfind('.//RunOn')):
        items.append(r)
    for r in gen(get_phrvb, iterfind('.//PhrVbEntry')):
        items.append(r)
    for r in gen(get_example, iterfind('.//EXAMPLE')):
        items.append(r)
    for r in gen(get_lexunit, iterfind('.//LEXUNIT')):
        items.append(r)
    for r in gen(get_simple, iterfind('.//PROPFORMPREP')):
        items.append(r)
    for r in gen(get_simple, iterfind('.//PROPFORM')):
        items.append(r)
    for r in gen(get_collocate, iterfind('.//Collocate')):
        items.append(r)
    for r in gen(get_exponent, iterfind('.//Exponent')):
        items.append(r)
    for r in gen(get_simple, iterfind('.//COLLO')):
        items.append(r)
    for r in gen(get_colloc, iterfind('.//COLLOC')):
        items.append(r)

    return (items, variations)
