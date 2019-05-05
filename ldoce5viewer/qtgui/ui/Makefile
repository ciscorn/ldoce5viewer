PYFILES := $(patsubst %.ui, %.py, $(wildcard *.ui))

all: __init__.py $(PYFILES)

__init__.py:
	touch $@

%.py: %.ui
	pyuic5 $< -o $@

.PYONY: clean
clean:
	rm -f $(PYFILES)

