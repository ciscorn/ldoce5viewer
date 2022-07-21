PYFILES := $(patsubst %.ui, %.py, $(wildcard *.ui))

all: __init__.py $(PYFILES)

__init__.py:
	touch $@

%.py: %.ui
	pyside6-uic $< -o $@

.PYONY: clean
clean:
	rm -f $(PYFILES)

