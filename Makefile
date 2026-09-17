.PHONY: install dev run test lint format clean

install:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

dev:
	cd src && fastapi dev main.py

run:
	cd src && fastapi run main.py

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/python -m black --check .
	.venv/bin/python -m flake8 .

format:
	.venv/bin/python -m black .

clean:
	find . -type d -name __pycache__ -not -path './.venv/*' -not -path './src/.venv/*' -prune -exec rm -rf {} +
