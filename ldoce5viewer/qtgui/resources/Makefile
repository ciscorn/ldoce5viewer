#!/usr/bin/make -f

FILES := $(wildcard *.png) $(wildcard *.svg) $(wildcard */*.png)

__init__.py: resource.qrc $(FILES)
	pyside6-rcc $< -o $@

.PHONY: clean
clean:
	rm -f __init__.py
