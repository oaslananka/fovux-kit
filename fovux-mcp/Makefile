.PHONY: help install test test-unit test-int lint format type-check audit check verify build-check clean docs serve-docs release

help:
	@echo "fovux MCP — available targets:"
	@echo "  install      Install dev dependencies via uv"
	@echo "  test         Run full test suite with coverage"
	@echo "  test-unit    Run unit tests only"
	@echo "  test-int     Run integration tests only"
	@echo "  lint         Run ruff check + mypy"
	@echo "  format       Run ruff format"
	@echo "  type-check   Run mypy --strict"
	@echo "  audit        Export locked runtime deps and run pip-audit"
	@echo "  check        Run the backend quality gate used before push"
	@echo "  build-check  Build the package locally to catch packaging regressions"
	@echo "  verify       Run check + docs + audit + build"
	@echo "  clean        Remove build artifacts"
	@echo "  docs         Build MkDocs site"
	@echo "  serve-docs   Serve docs locally"
	@echo "  release      Build wheel and sdist"

install:
	uv sync --frozen --extra dev
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

test:
	uv run pytest --cov=fovux --cov-report=term-missing --cov-report=html -x

test-unit:
	uv run pytest tests/unit/ -x -v

test-int:
	uv run pytest tests/integration/ -x -v

lint:
	uv lock --check
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run mypy --strict --warn-unused-ignores src/fovux/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

type-check:
	uv run mypy --strict --warn-unused-ignores src/fovux/

audit:
	uv lock --check
	uv export --no-dev --no-editable --no-hashes --output-file requirements-audit.txt
	uvx pip-audit -r requirements-audit.txt

check:
	python ../scripts/quality_gate.py mcp-check

build-check:
	python ../scripts/quality_gate.py mcp-build

verify:
	python ../scripts/quality_gate.py mcp-check
	python ../scripts/quality_gate.py mcp-docs
	python ../scripts/quality_gate.py mcp-audit
	python ../scripts/quality_gate.py mcp-build

clean:
	rm -rf build/ dist/ .eggs/ *.egg-info/ htmlcov/ .coverage coverage.xml .pytest_cache/ .mypy_cache/ .ruff_cache/

docs:
	uv run mkdocs build

serve-docs:
	uv run mkdocs serve

release:
	uv build
