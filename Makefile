.PHONY: install dev lint test build docker run clean help

help:
	@echo "Available targets:"
	@echo "  install    - Install production dependencies"
	@echo "  dev        - Install dev dependencies"
	@echo "  lint       - Run ruff linter"
	@echo "  test       - Run pytest"
	@echo "  build      - Build wheel package"
	@echo "  docker     - Build Docker image"
	@echo "  run        - Run MCP server locally"
	@echo "  clean      - Remove build artifacts"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/
	ruff format --check src/

format:
	ruff check --fix src/
	ruff format src/

test:
	pytest -v

build:
	pip wheel --no-deps -w dist .

docker:
	docker build -t vikunja-mcp-py:latest .

run:
	python -m src.server

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
