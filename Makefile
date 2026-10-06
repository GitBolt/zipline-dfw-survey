PY = .venv/bin/python
export PYTHONPATH = pipeline

.PHONY: test layers tracks all

test:
	PYTHONPATH=pipeline $(PY) -m pytest -q

layers:
	PYTHONPATH=pipeline $(PY) -m survey.fetch_layers

tracks:
	PYTHONPATH=pipeline $(PY) -m survey.fetch_tracks

all:
	PYTHONPATH=pipeline $(PY) -m survey.run
