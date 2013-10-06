'''Full-text searcher for headwords/phrases/examples/definitions'''

from __future__ import absolute_import

import re
import os.path
from operator import itemgetter
import fnmatch

from whoosh import index as wh_index
from whoosh.fields import Schema, STORED, IDLIST, ID, TEXT
from whoosh.analysis import StandardAnalyzer, Filter
from whoosh.query import Variations, Term, Or, And
from whoosh.qparser import QueryParser, \
    RangePlugin, BoostPlugin, WildcardPlugin, OperatorsPlugin
from whoosh.highlight import WholeFragmenter, HtmlFormatter
from whoosh.collectors import WrappingCollector, \
        UnlimitedCollector, TopCollector

from .utils.cdb import CDBReader, CDBMaker, CDBError
from .utils.text import normalize_token, normalize_index_key,\
    enc_utf8, dec_utf8


class IndexError(Exception):
    pass


class AbortableCollector(WrappingCollector):
    def __init__(self, child):
        WrappingCollector.__init__(self, child)
        self._aborted = False

    def collect_matches(self):
        collect = self.collect
        for sub_docnum in self.matches():
            if self._aborted:
                break
            collect(sub_docnum)

    @property
    def aborted(self):
        return self._aborted

    def abort(self):
        self._aborted = True


#-----------------
# Word Vatiations
#-----------------

class VariationsReader(object):
    def __init__(self, path):
        self._path = path
        self._reader = None
        self._reader = CDBReader(path)

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None

    def get_variations(self, word):
        r = set((word, ))
        try:
            s = self._reader[enc_utf8(word)]
        except KeyError:
            return r

        r.update(dec_utf8(w) for w in s.split(b'\0'))
        return r


class VariationsWriter(object):
    def __init__(self, f):
        self._writer = CDBMaker(f)

    def add(self, word, variations):
        self._writer.add(
            enc_utf8(word),
            b'\0'.join(enc_utf8(v) for v in variations))

    def finalize(self):
        self._writer.finalize()


def my_variations(var_reader):
    if var_reader:
        def f(fieldname, text, boost=1.0):
            return MyVariations(var_reader, fieldname, text, boost)
        return f
    else:
        return Term


class MyVariations(Variations):
    def __init__(self, var_reader, fieldname, text, boost=1.0):
        super(MyVariations, self).__init__(fieldname, text, boost)
        self.__var_reader = var_reader
        self.__fieldname = fieldname
        self.__text = text
        self.__boost = boost
        self.__cache = {}

    def _words(self, ixreader):
        cache = self.__cache
        text = self.text
        if text in cache:
            return cache[text]
        else:
            fieldname = self.fieldname
            words = [word for word in self.__var_reader.get_variations(text)
                     if (fieldname, word) in ixreader]
            cache[text] = words
            return words

    def __deepcopy__(self, x):
        return MyVariations(self.__var_reader,
                            self.__fieldname, self.__text, self.__boost)


#-----------------
# Index Schema
#-----------------

class _AccentFilter(Filter):
    def __call__(self, tokens):
        for t in tokens:
            t.text = normalize_token(t.text)
            yield t

_stopwords = frozenset(('a', 'an'))
_analyzer = (StandardAnalyzer(stoplist=_stopwords) | _AccentFilter())
_schema = Schema(
    content=TEXT(
        stored=True,
        spelling=True,
        analyzer=_analyzer),
    data=STORED,  # tuple (label, path, prio, sortkey)
    itemtype=ID,
    asfilter=IDLIST
)
_schema['content'].scorable = False


#-----------------
# Maker
#-----------------

class Maker(object):
    def __init__(self, index_dir):
        if os.path.exists(index_dir) and os.path.isfile(index_dir):
            os.unlink(index_dir)

        if not os.path.exists(index_dir):
            os.makedirs(index_dir)

        index = wh_index.create_in(index_dir, _schema)
        self._index = index
        self._writer = index.writer()
        self._committed = False

    def add_item(self,
                 itemtype, content, asfilter, label, path, prio, sortkey):
        self._writer.add_document(
            itemtype=itemtype,
            content=content,
            asfilter=asfilter,
            data=(label, path, prio, normalize_index_key(sortkey))
        )

    def commit(self):
        self._committed = True
        self._writer.commit()

    def close(self):
        if not self._committed:
            self._writer.cancel()

        self._index.close()
        self._index = None
        self._writer = None


#-----------------
# Searcher
#-----------------

class Searcher(object):
    def __init__(self, index_dir, var_path):
        self._index = None
        try:
            self._index = wh_index.open_dir(index_dir)
        except wh_index.IndexError:
            raise IndexError

        self._var_reader = self._make_var_reader(var_path)

        op = OperatorsPlugin(
            And=r"\bAND\b|&", Or=None,  # r"\bOR\b|\|",
            Not=r"\bNOT\b|\s+-", AndMaybe=None, Require=None)
        parser = QueryParser('content', _schema,
                             termclass=my_variations(self._var_reader))
        parser.remove_plugin_class(RangePlugin)
        parser.remove_plugin_class(BoostPlugin)
        parser.remove_plugin_class(WildcardPlugin)
        parser.replace_plugin(op)
        self._parser = parser

        parser_wild = QueryParser('content', _schema,
                                  termclass=my_variations(self._var_reader))
        parser_wild.remove_plugin_class(RangePlugin)
        parser_wild.remove_plugin_class(BoostPlugin)
        parser_wild.replace_plugin(op)
        self._parser_wild = parser_wild

        op_filter = OperatorsPlugin(And=r"\bAND\b", Or=r"\bOR\b",
                                    Not=None, AndMaybe=None, Require=None)
        asf_parser = QueryParser('asfilter', _schema)
        asf_parser.replace_plugin(op_filter)
        self._asf_parser = asf_parser

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def close(self):
        if self._index:
            self._index.close()
            self._index = None
        if self._var_reader:
            self._var_reader.close()

    def _make_var_reader(self, var_path):
        try:
            return VariationsReader(var_path)
        except (EnvironmentError, CDBError):
            return None

    def correct(self, misspelled, limit=5):
        with self._index.searcher() as searcher:
            corrector = searcher.corrector("content")
            return corrector.suggest(misspelled, limit)

    def make_collector(self, limit=None):
        if limit is None:
            return AbortableCollector(UnlimitedCollector())
        else:
            return AbortableCollector(TopCollector(limit))

    def search(self, collector, query_str1=None, query_str2=None,
               itemtypes=(), highlight=False):

        # rejects '*' and '?'
        if query_str1:
            for kw in (s.strip() for s in query_str1.split()):
                if not kw.replace("*", "").replace("?", "").strip():
                    return []

        wildcard = (query_str1 and any(c in query_str1 for c in "*?"))

        parser = self._parser_wild if wildcard else self._parser
        asf_parser = self._asf_parser

        with self._index.searcher() as searcher:
            andlist = []
            try:
                if query_str1:
                    andlist.append(parser.parse(query_str1))
                if query_str2:
                    andlist.append(asf_parser.parse(query_str2))
            except:
                return []

            if itemtypes:
                if len(itemtypes) > 1:
                    andlist.append(
                        Or([Term('itemtype', t) for t in itemtypes]))
                else:
                    andlist.append(Term('itemtype', itemtypes[0]))

            query = And(andlist)

            searcher.search_with_collector(query, collector)
            hits = collector.results()

            if highlight:
                hits.fragmenter = WholeFragmenter()
                hits.formatter = HtmlFormatter(
                    tagname='span', classname='s_match', termclass='s_term')

            if wildcard and query_str1:
                pat = query_str1.replace("-", "").replace(" ", "")
                wildmatch = re.compile(fnmatch.translate(pat))

            # Construct a result list
            results = []
            for hit in hits:
                if collector.aborted:
                    return []
                (label, path, prio, sortkey) = hit['data']

                if wildcard and query_str1:
                    if not wildmatch.match(sortkey):
                        continue

                if highlight:
                    if query_str1:
                        text = hit.highlights('content')
                    else:
                        text = hit['content']
                else:
                    text = None

                results.append((label, path, sortkey, prio, text))

            sortkey_prio_getter = itemgetter(2, 3)
            results.sort(key=sortkey_prio_getter)

            # Return
            return results

