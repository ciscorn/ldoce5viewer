"""Content transformer

This module generates HTML data from LDOCE5's XML documents.
"""

from html import escape

import lxml.etree as et

from ..utils.text import enc_utf8
from .transform_body import _trans_assets, body2html
from .utils import shorten_id


def _get_text_r(e):
    r = []
    if e.text is not None:
        r.append(e.text)

    for c in e:
        if c.tag != "span":
            r.append("<{0}>{1}</{0}>".format(c.tag, _get_text_r(c)))
        if c.tail is not None:
            r.append(c.tail)

    return "".join(r).strip()


def _get_text_nr(e):
    r = []
    if e.text is not None:
        r.append(e.text)

    for c in e:
        if c.tail is not None:
            r.append(c.tail)

    return "".join(r).strip()


def _build_header(resnames, title=None, meta={}):
    r = ['<!DOCTYPE html>\n<html lang="en">\n<head>\n' '<meta charset="utf-8">\n']

    for k in meta:
        v = meta[k]
        r.append('<meta name="{0}" content="{1}" />'.format(escape(k), escape(v)))

    r.append(
        '<script type="application/javascript" '
        'src="static:///scripts/jquery.js"></script>\n'
    )
    r.append(
        '<script type="application/javascript" '
        'src="static:///scripts/colorbox/jquery.colorbox.js"></script>\n'
    )
    r.append(
        '<link href="static:///scripts/colorbox/colorbox.css" '
        'rel="stylesheet" type="text/css">\n'
    )
    for name in resnames:
        r.append(
            '<link href="static:///styles/{0}.css" '
            'rel="stylesheet" type="text/css">\n'.format(name)
        )
        r.append(
            '<link href="static:///styles/{0}.css" '
            'rel="stylesheet" type="text/css">\n'.format(name)
        )
        r.append(
            '<script type="application/javascript" '
            'src="static:///scripts/{0}.js" ></script>\n'.format(name)
        )

    if title:
        r.append("<title>{0}</title>\n".format(title))

    r.append("</head>\n<body>\n")
    return "".join(r)


def trans_entry(data):
    r = []
    meta = {}

    try:
        root = et.fromstring(data)
        head = root.find("Head")
        title = _get_text_nr(head.find("HWD/BASE"))
        poslist = head.findall("POS")
        if poslist:
            title += " ({0})".format(", ".join(_get_text_nr(pos) for pos in poslist))
    except:
        title = ""

    try:
        pron_gb = head.find('Audio[@resource="GB_HWD_PRON"]')
        if pron_gb is not None:
            meta["gb_pron"] = pron_gb.get("topic").split("/")[-1]
        pron_us = head.find('Audio[@resource="US_HWD_PRON"]')
        if pron_us is not None:
            meta["us_pron"] = pron_us.get("topic").split("/")[-1]
    except:
        pass

    r.append(_build_header(["entry"], title=title, meta=meta))

    r.append(et.tounicode(_trans_assets(root), pretty_print=True, method="html"))

    r.append(body2html(root))
    r.append("</body></html>")
    return enc_utf8("".join(r))


def trans_thesaurus(data_set):
    r = []
    r.append(_build_header(["thesaurus"]))
    for data in data_set:
        root = et.fromstring(data)
        head = root.find("SECHEADING")
        if head is not None:
            r.append("<h2>{0}</h2>".format(head.text))

        for exp in root.iterfind("Exponent"):
            r.append('<div class="exponent">')
            head = exp.find("exp-head/EXP").text
            body = body2html(exp.find("exp-body"))
            r.append('<span class="colloc">{0}</span> {1}'.format(escape(head), body))
            r.append("</div>\n")

    r.append("</body>\n</html>")
    return enc_utf8("".join(r))


def trans_collocations(data):
    r = []
    r.append(_build_header(["collocations"]))
    root = et.fromstring(data)
    for cb in root.iterfind("ColloBox"):
        head = cb.find("HEADING")
        if head is not None:
            r.append("<h2>{0}</h2>\n".format(head.text))

        for sec in cb.iterfind("Section"):
            head = sec.find("SECHEADING")
            if head is not None:
                r.append("<h3>{0}</h3>\n".format(head.text))

            for co in sec.iterfind("Collocate"):
                r.append("<div class=collocate>")
                head = co.find("coll-head/COLLOC").text
                r.append("<span class=colloc>" + escape(head) + "</span> ")
                r.append(body2html(co.find("coll-body")))
                r.append("</div>")

    r.append("</body></html>")
    return enc_utf8("".join(r))


def trans_word_sets(data_set):
    r = []
    r.append(_build_header(["word_sets"]))
    for data in data_set:
        root = et.fromstring(data)
        name = root.find("ws-head/name").text
        number = root.find("ws-head/number").text
        r.append("<h2>{0} ({1})</h2>\n".format(name, number))
        r.append("<ul>\n")
        for ref in root.iterfind("ws-body/Ref"):
            hwd = ref.find("hwd").text or ""
            pos = ref.find("pos").text or ""
            topic = ref.get("topic")
            link = "/fs/" + shorten_id(topic)
            r.append(
                """<li><a href="{0}" class=hwd>{1}</a> """
                """<span class=pos>{2}</span>"""
                """</li>\n""".format(link, escape(hwd), escape(pos))
            )

        r.append("</ul>")

    r.append("</body></html>")
    return enc_utf8("".join(r))


def trans_phrases(data):
    r = []
    r.append(_build_header(["phrases"]))
    root = et.fromstring(data)
    for ph in root.iterfind("phrase"):
        ref = ph.find("phrase-head/Ref")
        topic = ref.get("topic")
        bookmark = ref.get("bookmark")
        phrase = ref.text
        link = "/fs/{0}#{1}".format(shorten_id(topic), shorten_id(bookmark))
        r.append('<h2><a href="{1}">{0}</a></h2>'.format(escape(phrase), link))
        r.append("<ul>")
        for e in (_get_text_r(e) for e in ph.iterfind("phrase-body/exa")):
            r.append("<li class=example>{0}</li>".format(e))

        r.append("</ul>")

    r.append("</body></html>")
    return enc_utf8("".join(r))


def trans_examples(data):
    root = et.fromstring(data)
    title = '{0} <span class="pos">{1}</span>'.format(
        root.find("exa-head/hwd").text, root.find("exa-head/pos").text
    )
    exas = tuple
    r = []
    r.append(_build_header(["examples"]))
    r.append("<h1>{0}</h1>\n".format(title))
    r.append("<ul>\n")
    for e in (_get_text_r(e) for e in root.iterfind("exa-body/exa")):
        r.append('<li class="example">{0}</li>\n'.format(e))

    r.append("</ul>\n")
    r.append("</body>\n</html>")
    return enc_utf8("".join(r))


def trans_word_families(data):
    r = []
    r.append(_build_header(["word_families"]))
    root = et.fromstring(data)
    for g in root.iterfind("group"):
        pos = g.find("pos").text
        r.append("<h2>{0}</h2>".format(pos))
        r.append("<ul>")
        for w in g.iterfind("w"):
            r.append("<li>")
            ref = w.find("Ref")
            if ref is not None:
                link = "/fs/" + shorten_id(ref.get("topic"))
                r.append(
                    '<a href="{0}" class=hwd>{1}</a>'.format(link, escape(ref.text))
                )
            else:
                r.append(_get_text_r(w))

            ref = w.find("opp/Ref")
            if ref is not None:
                link = "/fs/" + shorten_id(ref.get("topic"))
                r.append(
                    ' &#x2260; <a href="{0}" class=hwd>{1}</a>'.format(
                        link, escape(ref.text)
                    )
                )

            r.append("</li>\n")
        r.append("</ul>\n")

    r.append("</body>\n</html>")

    return enc_utf8("".join(r))


def trans_etymologies(data):
    r = []
    r.append(_build_header(["etymologies"]))
    root = et.fromstring(data)
    r.append(body2html(root))
    r.append("</body>\n</html>")
    return enc_utf8("".join(r))


def _trans_activator_concept(data, sid):
    r = []
    root = et.fromstring(data)
    cid = root.get("id")

    def section(e):
        nr = e.find("SECNR")
        if nr is not None:
            r.append('<div class="secnr">{0}.</div>\n'.format(_get_text_nr(nr)))

        cls = "section sel" if (e.get("id") == sid) else "section"
        r.append('<div class="{0}">\n'.format(cls))
        r.append(
            '<a href="dict:///activator/{cid}/{sid}">{text}</a>'.format(
                cid=cid, sid=e.get("id"), text=_get_text_nr(e)
            )
        )
        r.append("</div>\n")

    def ref(e):
        r.append(
            '<li><a href="dict:///activator/{cid}/{sid}">{text}</a></li>'.format(
                cid=e.get("topic"),
                sid=e.get("selection"),
                text=escape(e.text.replace("/", " / ")),
            )
        )

    def reference(e):
        reftype = e.find("REFTYPE")
        if reftype is not None:
            r.append('<span class="reftype">{0}</span>:'.format(escape(reftype.text)))

        r.append("<ul>")
        for cr in e.iterfind("Crossref/Ref"):
            ref(cr)

        r.append("</ul>")

    title = root.find("HWD").text
    r.append("<h1>{0}</h1>".format(escape(title.replace("/", " / "))))
    for e in root:
        if e.tag == "SUBHWD":
            r.append("<h2>{0}</h2>".format(escape(e.text.replace("/", " / "))))
        elif e.tag == "Section":
            section(e)

    r.append("<h2>Related Words</h2>")
    r.append("<ul>")
    for e in root.iterfind("References/Reference"):
        r.append("<li>")
        reference(e)
        r.append("</li>")

    r.append("</ul>")
    return "".join(r), title


def _trans_activator_section(data):
    r = []

    def exponent(e):
        r.append(body2html(e))

    root = et.fromstring(data)
    plain_title = title = _get_text_nr(root.find("SECDEF"))
    secnr = root.find("SECDEF/SECNR")
    if secnr is not None:
        nr = secnr.text.strip()
        plain_title = "({0}) - {1}".format(nr, title)
        title = "{0}. {1}".format(nr, title)

    r.append("<h1>{0}</h1>".format(title))
    for e in root.iterfind("Exponent"):
        exponent(e)

    return "".join(r), plain_title


def trans_activator(data_c, data_s, sid):
    r = []
    (concept_body, concept_title) = _trans_activator_concept(data_c, sid)
    (section_body, section_title) = _trans_activator_section(data_s)
    title = concept_title + section_title
    r.append(_build_header(["activator"], title=title))
    # section
    r.append('<div id="section_w">\n')
    r.append('<div id="section">\n')
    r.append(section_body)
    r.append("</div>\n")
    r.append("</div>\n")
    # concept
    r.append('<div id="concept">\n')
    r.append(concept_body)
    r.append("</div>\n")
    # end
    r.append("</body></html>")
    return enc_utf8("".join(r))
