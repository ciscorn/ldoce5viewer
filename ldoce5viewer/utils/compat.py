#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

try:
    import __builtin__ as builtins
except:
    import builtins

import itertools

range = getattr(builtins, 'xrange', builtins.range)
basestring = getattr(builtins, 'basestring', str)
zip = getattr(itertools, 'izip', zip)

