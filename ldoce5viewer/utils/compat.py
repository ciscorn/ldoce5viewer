#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import builtins
import itertools

range = getattr(builtins, "xrange", builtins.range)
basestring = getattr(builtins, "basestring", str)
zip = getattr(itertools, "izip", zip)
