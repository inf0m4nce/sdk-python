.PHONY: all test lint build clean install dev help typecheck

# Default target
all: lint test build

# Install package
install:
	pip install -e .

# Install with dev dependencies
dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-coverage:
	pytest tests/ --cov=infomance --cov-report=html --cov-report=term-missing --cov-fail-under=80
	@echo "Coverage report: htmlcov/index.html"

# Run linter
lint:
	ruff check infomance/ tests/
	ruff format --check infomance/ tests/

# Fix lint issues
lint-fix:
	ruff check --fix infomance/ tests/
	ruff format infomance/ tests/

# Type check
typecheck:
	mypy infomance/ --ignore-missing-imports

# Build package
build:
	pip install build
	python -m build

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Security scan
security:
	pip install safety bandit
	safety check || true
	bandit -r infomance/ -ll

# Publish to PyPI (requires TWINE_USERNAME and TWINE_PASSWORD)
publish: clean build
	pip install twine
	twine upload dist/*

# Publish to TestPyPI
publish-test: clean build
	pip install twine
	twine upload --repository testpypi dist/*

# Check if package can be published
check-publish: build
	pip install twine
	twine check dist/*

# Help
help:
	@echo "Infomance Python SDK - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make install       - Install package"
	@echo "  make dev           - Install with dev dependencies"
	@echo "  make test          - Run tests"
	@echo "  make test-coverage - Run tests with coverage"
	@echo "  make lint          - Run linter"
	@echo "  make lint-fix      - Fix lint issues"
	@echo "  make typecheck     - Run type checker"
	@echo "  make build         - Build package"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make security      - Run security scan"
	@echo "  make publish       - Publish to PyPI"
	@echo "  make publish-test  - Publish to TestPyPI"
	@echo "  make check-publish - Check if package can be published"
	@echo "  make help          - Show this help"
