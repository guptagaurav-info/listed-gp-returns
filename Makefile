PY ?= python
export PYTHONPATH := src

.PHONY: all ingest run test
all: ingest run
ingest:
	$(PY) -m lgp.ingest
run:
	$(PY) -m lgp.pipeline
test:
	$(PY) -m pytest -q tests
