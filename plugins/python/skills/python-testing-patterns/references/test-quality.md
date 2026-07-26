# Test Quality and Anti-Patterns

Read this before writing tests, and again whenever you're about to add a mock.

## What a Good Test Is

A good test verifies behavior through the code's public interface, not its internal structure. Code can be refactored entirely; a good test shouldn't need to change, because it never depended on *how* the behavior was implemented — only on *what* it does. It reads like a specification: the name states the capability, the body proves it holds.

- One behavior per test
- Uses the public API only, not private methods or internals
- Expected values come from an independent source of truth (a known literal, a worked example) — never recomputed the same way the code computes them
- Survives refactors that don't change behavior

## Anti-Pattern: Implementation-Coupled Tests

Coupled to internal structure instead of the public interface. The tell: the test breaks when you refactor, even though behavior hasn't changed.

```python
# BAD: mocks an internal collaborator and asserts on the call itself
def test_checkout_charges_payment_service(mocker):
    mock_payment = mocker.patch.object(checkout_module, "_payment_service")
    checkout(cart, payment_method)
    mock_payment.process.assert_called_once_with(cart.total)

# GOOD: exercises the real checkout, asserts on observable outcome
def test_checkout_confirms_order_for_valid_cart():
    cart = create_cart_with(product)
    result = checkout(cart, valid_payment_method)
    assert result.status == "confirmed"
```

```python
# BAD: bypasses the interface to verify — queries storage directly
def test_create_user_saves_to_database(db_conn):
    create_user(name="Alice")
    row = db_conn.execute("SELECT * FROM users WHERE name = ?", ("Alice",)).fetchone()
    assert row is not None

# GOOD: verifies through the interface the caller would actually use
def test_create_user_makes_user_retrievable():
    user = create_user(name="Alice")
    assert get_user(user.id).name == "Alice"
```

## Anti-Pattern: Tautological Tests

The expected value is recomputed the same way the code computes it, so the test passes by construction and can never disagree with the code.

```python
# BAD: expected value is derived with the same logic as the code under test
def test_calculate_total_sums_line_items():
    items = [{"price": 10}, {"price": 5}]
    expected = sum(item["price"] for item in items)
    assert calculate_total(items) == expected

# GOOD: expected value is an independent, known literal
def test_calculate_total_sums_line_items():
    assert calculate_total([{"price": 10}, {"price": 5}]) == 15
```

## Anti-Pattern: Testing Mock Behavior Instead of Real Behavior

Patching the function under test (rather than its external dependency) proves the patch works, not that the code works.

```python
# BAD: patches the function being tested — nothing real ever executes
def test_get_user_returns_user(mocker):
    mocker.patch("myapp.service.get_user", return_value=User(id=1, name="Alice"))
    result = service.get_user(1)
    assert result.name == "Alice"  # only proves the patch was applied

# GOOD: the function under test runs for real; only its external dependency is mocked
def test_get_user_returns_user(mocker):
    mocker.patch("myapp.service.db.fetch_user", return_value={"id": 1, "name": "Alice"})
    result = service.get_user(1)
    assert result.name == "Alice"  # proves get_user's own mapping logic is correct
```

## Anti-Pattern: Mocking Without Understanding Dependencies

Mocking a method hides side effects that the rest of the test — or a later assertion — depends on.

```python
# BAD: mocking discover_tools also suppresses the config write it normally performs
def test_duplicate_server_rejected(mocker):
    mocker.patch("myapp.catalog.discover_tools", return_value=None)

    register_server(config)
    # should raise DuplicateServerError — but config.json was never
    # written, so the duplicate check never fires
    register_server(config)

# GOOD: mock only the slow/external part; preserve the side effect the test needs
def test_duplicate_server_rejected(mocker):
    mocker.patch("myapp.catalog.probe_server_over_network")  # slow I/O, not the config write

    register_server(config)
    with pytest.raises(DuplicateServerError):
        register_server(config)
```

Before mocking anything, ask what side effects the real method has and whether the test — now or later — depends on any of them. If unsure, run the real implementation first and observe what it actually does before deciding what to mock.

## Anti-Pattern: Incomplete Mocks

A mock built from only the fields the current test happens to use hides structural assumptions; downstream code that reads an omitted field fails silently or passes for the wrong reason.

```python
# BAD: partial mock, missing fields the real response includes
mock_response = {"status": "success", "data": {"user_id": "123"}}
# breaks later when code reads response["metadata"]["request_id"]

# GOOD: mirrors the real response shape completely
mock_response = {
    "status": "success",
    "data": {"user_id": "123"},
    "metadata": {"request_id": "req-789", "timestamp": 1234567890},
}
```

## Anti-Pattern: Test-Only Methods on Production Classes

A method that exists only to support test cleanup pollutes the production class and risks being called for real.

```python
# BAD: teardown() only ever called from tests
class SessionManager:
    def teardown(self):
        self._workspace.destroy()

# GOOD: test-only cleanup lives in test utilities, using the public interface
# tests/utils.py
def cleanup_session(manager: SessionManager, workspaces: WorkspaceRegistry) -> None:
    workspace = manager.get_workspace_info()
    if workspace:
        workspaces.destroy(workspace.id)
```

## Mocking Discipline — Boundaries Only

Mock at **system boundaries**, not your own code:

- External APIs (payment, email, third-party HTTP)
- Databases — prefer a real test database (e.g., sqlite in-memory) over mocking the DB layer when feasible
- Time and randomness
- The filesystem (sometimes)

Don't mock your own classes, modules, or anything you control.

A countable warning sign that mocking has gone too far: if the mock setup is longer than the test's actual assertions, or you can't explain in one sentence why a particular mock is needed, that's a smell — reconsider whether an integration-style test with real collaborators would be simpler.

## Testability Smells (Flag, Don't Fix Silently)

When existing code makes a boundary hard to reach cleanly, that's a smell in the code — not a reason to mock around it with increasing contortion.

```python
# Hard to mock — the client is constructed inside the function
def send_receipt(order):
    client = SmtpClient(host=settings.SMTP_HOST)
    client.send(order.customer_email, ...)

# Easy to mock, and non-breaking for existing callers — the client is
# an optional parameter that defaults to today's behavior
def send_receipt(order, client: SmtpClient | None = None):
    client = client or SmtpClient(host=settings.SMTP_HOST)
    client.send(order.customer_email, ...)
```

If the code you're testing looks like the first example, flag it and ask whether to write an integration-style test around the friction (accept it) or refactor the code for injectability. Don't refactor without asking first — and remember this code already has callers, so any signature change needs a non-breaking path like the optional-parameter form above, not a silent breaking change.

## Quick Reference

| Anti-Pattern | Fix |
|---|---|
| Implementation-coupled | Test through the public interface, not internals |
| Tautological | Expected value must be an independent literal |
| Testing mock behavior | Patch the dependency, not the function under test |
| Mocking without understanding | Understand side effects before mocking; mock minimally |
| Incomplete mocks | Mirror the real response/object shape completely |
| Test-only methods in production | Move cleanup into test utilities |
| Hard-to-mock boundary | Flag as a testability smell; ask before refactoring |
