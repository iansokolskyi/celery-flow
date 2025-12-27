.PHONY: check types lint format test coverage clean

# Full verification suite - run after every change
check: types lint test
	@echo "✅ All checks passed"

# Individual checks
types:
	mypy src/ --strict

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

test:
	pytest --cov=celery_flow --cov-report=term-missing --cov-fail-under=80

# Run tests without coverage (faster iteration)
test-fast:
	pytest -x -q

# Run only unit tests
test-unit:
	pytest tests/unit/ -v

# Run integration tests
test-integration:
	pytest -m integration -v

# Show coverage report
coverage:
	pytest --cov=celery_flow --cov-report=html
	@echo "Open htmlcov/index.html to view coverage report"

# Clean build artifacts
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

