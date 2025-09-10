# Testing Guide for Agents Project

This document provides comprehensive information about the testing infrastructure and how to run tests for the Agents project.

## Table of Contents

- [Testing Framework](#testing-framework)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Coverage Reporting](#coverage-reporting)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [Continuous Integration](#continuous-integration)

## Testing Framework

The project uses **pytest** as the primary testing framework with the following key dependencies:

- `pytest` - Core testing framework
- `pytest-cov` - Coverage reporting
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `pytest-httpx` - HTTP testing utilities
- `fakeredis` - Redis testing utilities
- `factory-boy` - Test data factories

### Installing Test Dependencies

For testing only, you can install just the test dependencies:

```bash
pip install -r requirements-test.txt
```

For full development including all project dependencies:

```bash
pip install -r requirements.txt
```

**Note**: The main requirements.txt has resolved dependency conflicts between `httpx`, `langfuse`, `fastmcp`, and `pytest-httpx` by using compatible version ranges.

## Test Structure

```
tests/
├── conftest.py              # Shared test configuration and fixtures
├── __init__.py
├── unit/                    # Unit tests
│   ├── agents/             # Agent-related unit tests
│   ├── core/               # Core module tests
│   ├── infrastructure/     # Infrastructure tests
│   └── integrations/       # Integration module tests
├── integration/            # Integration tests
│   └── test_api_endpoints.py
├── performance/            # Performance tests
│   └── test_load_testing.py
└── fixtures/               # Test data and fixtures
```

## Running Tests

### Using the Test Runner Script

The project includes convenient test runner scripts:

#### Test Runner (requires all dependencies)
```bash
# Run unit tests
python run_tests.py

# Run with coverage
python run_tests.py --coverage --html-cov

# Run specific test types
python run_tests.py --type integration
python run_tests.py --type performance
python run_tests.py --type all

# Run specific test files
python run_tests.py tests/unit/agents/test_base_agent_server.py

# Run fast tests only (skip slow tests)
python run_tests.py --fast

# Verbose output
python run_tests.py --verbose
```

### Using pytest Directly

```bash
# Basic test run
pytest tests/unit

# With coverage
pytest tests/unit --cov=src --cov-report=html

# Run specific test categories
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m performance       # Performance tests only
pytest -m "not slow"        # Skip slow tests

# Run specific test files
pytest tests/unit/agents/test_base_agent_server.py

# Verbose output
pytest tests/unit -v

# Stop on first failure
pytest tests/unit -x
```

## Coverage Reporting

The project is configured to generate comprehensive coverage reports:

### Configuration

Coverage settings are defined in:
- `pytest.ini` - Pytest configuration with coverage settings
- `.coveragerc` - Detailed coverage configuration

### Coverage Reports

Coverage reports are generated in multiple formats:

1. **Terminal Output** - Shows missing lines in console
2. **HTML Report** - Interactive HTML report in `htmlcov/` directory
3. **XML Report** - Machine-readable `coverage.xml` for CI/CD

### Coverage Targets

- **Minimum Coverage**: 80% (configurable in pytest.ini)
- **Exclusions**: Test files, migrations, settings, and other non-testable code

## Test Categories

Tests are organized into categories using pytest markers:

### Unit Tests (`@pytest.mark.unit`)
- Fast, isolated tests
- Test individual functions/classes
- Use mocks for external dependencies
- Should run in under 1 second each

### Integration Tests (`@pytest.mark.integration`)
- Test component interactions
- May use real services in isolated environments
- Test API endpoints end-to-end
- Moderate execution time (1-10 seconds)

### Performance Tests (`@pytest.mark.performance`)
- Load testing and benchmarks
- Memory usage validation
- Response time requirements
- May take longer to execute

### Specialized Markers
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.redis` - Tests requiring Redis
- `@pytest.mark.external` - Tests requiring external services

## Writing Tests

### Test Structure Guidelines

```python
"""
Module docstring describing what's being tested.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.module_under_test import ClassUnderTest


class TestClassUnderTest:
    """Test cases for ClassUnderTest."""

    @pytest.fixture
    def mock_dependency(self):
        """Create mock dependency for testing."""
        return MagicMock()

    def test_method_success_case(self, mock_dependency):
        """Test successful execution of method."""
        # Arrange
        instance = ClassUnderTest(mock_dependency)

        # Act
        result = instance.method_under_test()

        # Assert
        assert result is not None
        mock_dependency.some_method.assert_called_once()

    def test_method_error_case(self, mock_dependency):
        """Test error handling in method."""
        # Arrange
        mock_dependency.some_method.side_effect = Exception("Test error")
        instance = ClassUnderTest(mock_dependency)

        # Act & Assert
        with pytest.raises(Exception, match="Test error"):
            instance.method_under_test()
```

### Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **Follow AAA pattern** - Arrange, Act, Assert
3. **One assertion per test** when possible
4. **Use fixtures** for common test setup
5. **Mock external dependencies** in unit tests
6. **Test both success and failure cases**
7. **Use parametrized tests** for multiple input scenarios

### Fixtures

Common fixtures are available in `conftest.py`:

- `mock_llm` - Mock language model
- `temp_config_file` - Temporary configuration file
- `test_config` - Test configuration instance
- `mock_redis` - Mock Redis client
- `sample_meeting_notes` - Sample test data

## Test Configuration

### Environment Variables

Tests use specific environment variables to avoid conflicts:

```python
os.environ["MODEL_API_KEY"] = "test_api_key_12345"
os.environ["LANGFUSE_SECRET_KEY"] = "test_secret_key"
os.environ["LANGFUSE_PUBLIC_KEY"] = "test_public_key"
os.environ["REDIS_PASSWORD"] = "test_password"
os.environ["LOG_LEVEL"] = "DEBUG"
```

### Pytest Configuration

Key settings in `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests
addopts =
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --cov=src
    --cov-report=html:htmlcov
    --cov-report=xml:coverage.xml
    --cov-report=term-missing
    --cov-fail-under=80
```

## Continuous Integration

### GitHub Actions Integration

For CI/CD, add the following to your workflow:

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt

- name: Run tests with coverage
  run: |
    python run_tests.py --coverage --type all

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### Pre-commit Hooks

Consider adding test execution to pre-commit hooks:

```yaml
- repo: local
  hooks:
    - id: pytest-check
      name: pytest-check
      entry: python run_tests.py --fast
      language: system
      pass_filenames: false
      always_run: true
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes the project root
2. **Missing Dependencies**: Install test requirements: `pip install -r requirements.txt`
3. **Slow Tests**: Use `--fast` flag to skip slow tests during development
4. **Coverage Issues**: Check `.coveragerc` for exclusion patterns

### Debug Mode

Run tests in debug mode for troubleshooting:

```bash
pytest tests/unit/agents/test_base_agent_server.py -v -s --tb=long
```

### Useful Commands

```bash
# List all available test markers
pytest --markers

# Dry run to see what tests would be executed
pytest --collect-only tests/

# Run tests matching a pattern
pytest -k "test_method_name"

# Profile test execution time
pytest --durations=10 tests/
```

## Contributing

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Add appropriate markers (`@pytest.mark.unit`, etc.)
3. Include both positive and negative test cases
4. Update this documentation if adding new test categories
5. Ensure tests pass locally before submitting PRs

For questions or issues with the testing infrastructure, please open an issue in the project repository.
