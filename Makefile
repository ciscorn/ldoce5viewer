PKG := ldoce5viewer
PYTHON := python

runqt: qtui qtresource
	$(PYTHON) ./ldoce5viewer.py

sdist: precompile
	$(PYTHON) ./setup.py sdist

precompile: qtui qtresource

qtui:
	cd $(PKG)/qtgui/ui/; $(MAKE)

qtresource:
	cd $(PKG)/qtgui/resources/; $(MAKE)

build: precompile
	$(PYTHON) ./setup.py build

install: build
	$(PYTHON) ./setup.py install


.PHONY: clean clean-build
clean: clean-build
	cd $(PKG)/qtgui/ui/; $(MAKE) clean
	cd $(PKG)/qtgui/resources/; $(MAKE) clean

clean-build:
	rm -rf build
	rm -rf dist
	rm -f MANIFEST

