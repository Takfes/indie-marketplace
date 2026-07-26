---
name: python-testing-patterns
description: Write a pytest suite for Python code that already exists — plan coverage across the public interface, confirm ambiguous behavior with the user, then write and verify tests with disciplined mocking. Use once a script or module is finished and needs tests.
---

# Python Testing Patterns

Comprehensive guide to writing a pytest suite for Python code that's already been written — planning coverage, confirming intent with the author, and avoiding the anti-patterns that make tests worthless.

## When to Use This Skill

- Writing tests for a script or module you just finished
- Backfilling tests for existing code that has none
- Extending coverage on code someone else wrote
- Mocking external dependencies and services
- Testing async code and concurrent operations
- Setting up continuous testing in CI/CD
- Implementing property-based testing
- Testing database operations
- Debugging failing tests

## Core Concepts

### 1. Test Types

- **Unit Tests**: Test individual functions/classes in isolation
- **Integration Tests**: Test interaction between components
- **Functional Tests**: Test complete features end-to-end
- **Performance Tests**: Measure speed and resource usage

### 2. Test Structure (AAA Pattern)

- **Arrange**: Set up test data and preconditions
- **Act**: Execute the code under test
- **Assert**: Verify the results

### 3. Test Coverage

- Measure what code is exercised by tests
- Identify untested code paths
- Aim for meaningful coverage, not just high percentages

### 4. Test Isolation

- Tests should be independent
- No shared state between tests
- Each test should clean up after itself

## Workflow: Testing Code That Already Exists

This skill is for writing tests *after* the code exists, not test-first. That reordering changes the discipline: there's no "watch it fail before the code exists" step, so the rigor has to come from planning coverage deliberately and verifying tests can actually fail.

Read [references/test-quality.md](references/test-quality.md) before writing any test — it covers what makes a test worth keeping, the anti-patterns to avoid, and mocking discipline.

### 1. Plan before writing anything

Scan the finished code and enumerate its **seams** — the public functions, classes, and CLI entry points you'll test through, as opposed to internals you won't reach into directly. For each seam, note the scenarios worth covering (happy path, error/edge cases, boundary values), and flag any seam where the intended behavior isn't obvious from reading the code.

Present the plan as a chat checklist before writing any test code:

```
## Test Plan: orders.py

| Seam                           | Scenarios                                  | Notes |
|---------------------------------|---------------------------------------------|-------|
| create_order(items, customer)  | happy path; empty items; unknown customer  | — |
| apply_discount(order, code)    | valid code; expired code; unknown code     | ambiguous — reject on expiry, or apply pre-expiry rate? |
```

Don't save this plan by default. Only write it to a file if the user asks.

### 2. Resolve ambiguity before writing those tests

Batch every seam flagged as ambiguous and ask the user directly what the intended behavior is. This is a hard gate for those specific seams — don't guess and don't write the test until answered. It isn't a hard gate on the whole plan: write and run tests for the unambiguous seams while waiting on an answer, rather than blocking everything on one unclear function.

### 3. Write one seam at a time, run immediately

Write the test(s) for one seam, then run pytest and confirm it passes. A failure here means either the code has a bug or the test encodes the wrong expectation — surface it, don't silently rewrite the assertion to match whatever the code happens to output.

### 4. Prove non-trivial tests can actually fail

For tests covering real logic or branching, briefly break the behavior under test — comment out a line, flip a condition, change a boundary — confirm the test now fails, then revert. This is a stand-in for the "watch it fail" discipline TDD gets for free, applied after the fact. Apply it selectively: skip it for trivial passthroughs or simple getters where a broken implementation obviously couldn't pass anyway.

### 5. Flag testability smells, don't fix them silently

If the code makes a boundary hard to reach cleanly — e.g., a function instantiates its own client instead of accepting one — that's a smell in the code, not a reason to mock around it with increasing contortion. Flag it and ask whether to test around the friction (accept an integration-style test) or refactor for injectability. Never refactor without asking first.

## Quick Start

```python
# test_example.py
def add(a, b):
    return a + b

def test_add():
    """Basic test example."""
    result = add(2, 3)
    assert result == 5

def test_add_negative():
    """Test with negative numbers."""
    assert add(-1, 1) == 0

# Run with: pytest test_example.py
```

## Detailed patterns and worked examples

Detailed pattern documentation lives in `references/details.md`. Read that file when the navigation tier above is insufficient.

## Testing Best Practices

### Test Organization

```python
# tests/
#   __init__.py
#   conftest.py           # Shared fixtures
#   test_unit/            # Unit tests
#     test_models.py
#     test_utils.py
#   test_integration/     # Integration tests
#     test_api.py
#     test_database.py
#   test_e2e/            # End-to-end tests
#     test_workflows.py
```

### Test Naming Convention

A common pattern: `test_<unit>_<scenario>_<expected_outcome>`. Adapt to your team's preferences.

```python
# Pattern: test_<unit>_<scenario>_<expected>
def test_create_user_with_valid_data_returns_user():
    ...

def test_create_user_with_duplicate_email_raises_conflict():
    ...

def test_get_user_with_unknown_id_returns_none():
    ...

# Good test names - clear and descriptive
def test_user_creation_with_valid_data():
    """Clear name describes what is being tested."""
    pass

def test_login_fails_with_invalid_password():
    """Name describes expected behavior."""
    pass

def test_api_returns_404_for_missing_resource():
    """Specific about inputs and expected outcomes."""
    pass

# Bad test names - avoid these
def test_1():  # Not descriptive
    pass

def test_user():  # Too vague
    pass

def test_function():  # Doesn't explain what's tested
    pass
```

### Testing Retry Behavior

Verify that retry logic works correctly using mock side effects.

```python
from unittest.mock import Mock

def test_retries_on_transient_error():
    """Test that service retries on transient failures."""
    client = Mock()
    # Fail twice, then succeed
    client.request.side_effect = [
        ConnectionError("Failed"),
        ConnectionError("Failed"),
        {"status": "ok"},
    ]

    service = ServiceWithRetry(client, max_retries=3)
    result = service.fetch()

    assert result == {"status": "ok"}
    assert client.request.call_count == 3

def test_gives_up_after_max_retries():
    """Test that service stops retrying after max attempts."""
    client = Mock()
    client.request.side_effect = ConnectionError("Failed")

    service = ServiceWithRetry(client, max_retries=3)

    with pytest.raises(ConnectionError):
        service.fetch()

    assert client.request.call_count == 3

def test_does_not_retry_on_permanent_error():
    """Test that permanent errors are not retried."""
    client = Mock()
    client.request.side_effect = ValueError("Invalid input")

    service = ServiceWithRetry(client, max_retries=3)

    with pytest.raises(ValueError):
        service.fetch()

    # Only called once - no retry for ValueError
    assert client.request.call_count == 1
```

### Mocking Time with Freezegun

Use freezegun to control time in tests for predictable time-dependent behavior.

```python
from freezegun import freeze_time
from datetime import datetime, timedelta

@freeze_time("2026-01-15 10:00:00")
def test_token_expiry():
    """Test token expires at correct time."""
    token = create_token(expires_in_seconds=3600)
    assert token.expires_at == datetime(2026, 1, 15, 11, 0, 0)

@freeze_time("2026-01-15 10:00:00")
def test_is_expired_returns_false_before_expiry():
    """Test token is not expired when within validity period."""
    token = create_token(expires_in_seconds=3600)
    assert not token.is_expired()

@freeze_time("2026-01-15 12:00:00")
def test_is_expired_returns_true_after_expiry():
    """Test token is expired after validity period."""
    token = Token(expires_at=datetime(2026, 1, 15, 11, 30, 0))
    assert token.is_expired()

def test_with_time_travel():
    """Test behavior across time using freeze_time context."""
    with freeze_time("2026-01-01") as frozen_time:
        item = create_item()
        assert item.created_at == datetime(2026, 1, 1)

        # Move forward in time
        frozen_time.move_to("2026-01-15")
        assert item.age_days == 14
```

### Test Markers

```python
# test_markers.py
import pytest

@pytest.mark.slow
def test_slow_operation():
    """Mark slow tests."""
    import time
    time.sleep(2)


@pytest.mark.integration
def test_database_integration():
    """Mark integration tests."""
    pass


@pytest.mark.skip(reason="Feature not implemented yet")
def test_future_feature():
    """Skip tests temporarily."""
    pass


@pytest.mark.skipif(os.name == "nt", reason="Unix only test")
def test_unix_specific():
    """Conditional skip."""
    pass


@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug():
    """Mark expected failures."""
    assert False


# Run with:
# pytest -m slow          # Run only slow tests
# pytest -m "not slow"    # Skip slow tests
# pytest -m integration   # Run integration tests
```

### Coverage Reporting

```bash
# Install coverage
pip install pytest-cov

# Run tests with coverage
pytest --cov=myapp tests/

# Generate HTML report
pytest --cov=myapp --cov-report=html tests/

# Fail if coverage below threshold
pytest --cov=myapp --cov-fail-under=80 tests/

# Show missing lines
pytest --cov=myapp --cov-report=term-missing tests/
```

For advanced patterns (async testing, monkeypatching, property-based testing, database testing, CI/CD integration, and configuration), see [references/advanced-patterns.md](references/advanced-patterns.md)
