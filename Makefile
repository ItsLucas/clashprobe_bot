PY?=python3
PIP?=pip3
VENV?=.venv

.PHONY: help
help:
	@echo "Targets: init, dev, run, configure, lint, test, docker"

.PHONY: init
init:
	$(PY) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip
	. $(VENV)/bin/activate && pip install -r requirements.txt

.PHONY: dev
dev:
	. $(VENV)/bin/activate && python -m src.main

.PHONY: run
run:
	$(PY) -m src.main

.PHONY: configure
configure:
	$(PY) scripts/setup_config.py

.PHONY: lint
lint:
	. $(VENV)/bin/activate && flake8 src

.PHONY: test
test:
	. $(VENV)/bin/activate && pytest -q

.PHONY: docker
docker:
	docker build -t clashprobe-bot:latest .
