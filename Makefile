PKG := ldoce5viewer
PYTHON := python

build: precompile
	$(PYTHON) ./setup.py build

install: build
	$(PYTHON) ./setup.py install
	cp ./ldoce5viewer.desktop /usr/share/applications/
	cp ./ldoce5viewer/qtgui/resources/ldoce5viewer.svg /usr/share/pixmaps/
	[ -x /usr/bin/update-desktop-database ] && sudo update-desktop-database -q

sdist: precompile
	$(PYTHON) ./setup.py sdist

precompile: qtui qtresource

qtui:
	cd $(PKG)/qtgui/ui/; $(MAKE)

qtresource:
	cd $(PKG)/qtgui/resources/; $(MAKE)

.PHONY: clean clean-build
clean: clean-build
	cd $(PKG)/qtgui/ui/; $(MAKE) clean
	cd $(PKG)/qtgui/resources/; $(MAKE) clean

clean-build:
	rm -rf build
	rm -rf dist
	rm -f MANIFEST

