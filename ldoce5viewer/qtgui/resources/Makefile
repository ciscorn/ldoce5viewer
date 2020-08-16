#!/usr/bin/make -f

FILES := $(wildcard *.png) $(wildcard *.svg) $(wildcard */*.png)

__init__.py: resource.qrc $(FILES)
	pyrcc5 $< -o $@

.PHONY: clean
clean:
	rm -f __init__.py
