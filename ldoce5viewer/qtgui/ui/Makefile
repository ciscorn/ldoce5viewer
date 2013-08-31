PYFILES := $(patsubst %.ui, %.py, $(wildcard *.ui))

all: __init__.py $(PYFILES)

__init__.py:
	touch $@

%.py: %.ui
	pyuic4 $< -o $@

.PYONY: clean
clean:
	rm -f $(PYFILES)

