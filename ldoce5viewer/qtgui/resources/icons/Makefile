#!/usr/bin/make -f

PNG_SRC := $(patsubst %.svg, %-src.png, $(wildcard *.svg))
PNG_24 := $(patsubst %-src.png, %-24.png, $(PNG_SRC))
PNG_22 := $(patsubst %-src.png, %-22.png, $(PNG_SRC))
PNG_16 := $(patsubst %-src.png, %-16.png, $(PNG_SRC))

all: $(PNG_24) $(PNG_22) $(PNG_16)

%-48-src.png: %.svg icongen.py
	inkscape -w 96 -h 96 -e $@ $<

edit-clear-48.png: edit-clear-48-src.png
	cp $< $@

%-48.png: %-48-src.png
	python2 icongen.py $< $@

%-24.png: %-48.png
	convert $< -filter Lanczos -resize 24x24 $@

%-22.png: %-48.png
	convert $< -filter Lanczos -resize 22x22 $@

%-16.png: %-48.png
	convert $< -filter Lanczos -resize 16x16 $@

.PHONY: clean
clean:
	rm -f *.png

