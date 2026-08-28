# Refactoring Patterns Reference

Structural moves only, with complete before/after examples. Idiom-level patterns -- guard clauses, dictionary dispatch, match statements, named boolean conditions, naming conventions, magic-number extraction -- are catalogued in `python-patterns`, not here.

## Table of Contents

1. [Extract Method](#1-extract-method)
2. [Encapsulate Global State](#2-encapsulate-global-state)
3. [Group Related Functions](#3-group-related-functions)
4. [Create Domain Models](#4-create-domain-models)
5. [Apply Dependency Injection](#5-apply-dependency-injection)

---

## 1. Extract Method

**Problem:** Long functions that do multiple things are hard to understand and test.

**Solution:** Extract logical chunks into well-named helper functions.

```python
# BEFORE: 60-line function doing everything
def process_order(order_id):
    # Fetch order (10 lines of error handling and DB logic)
    order = db.query(Order).filter_by(id=order_id).first()
    if not order:
        log.error(f"Order not found: {order_id}")
        return None

    # Validate order (15 lines of validation logic)
    if not order.items:
        log.error(f"Empty order: {order_id}")
        return None
    for item in order.items:
        if item.quantity <= 0:
            log.error(f"Invalid quantity: {item.quantity}")
            return None
        product = db.query(Product).filter_by(id=item.product_id).first()
        if not product or product.stock < item.quantity:
            log.error(f"Insufficient stock for product: {item.product_id}")
            return None

    # Calculate total (10 lines of price calculation)
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * 0.08
    shipping = 10.0 if subtotal < 50 else 0.0
    total = subtotal + tax + shipping

    # Process payment (15 lines of payment logic)
    payment_method = order.payment_method
    if payment_method == 'credit':
        result = process_credit_card(order.card_token, total)
    elif payment_method == 'paypal':
        result = process_paypal(order.paypal_email, total)
    else:
        log.error(f"Invalid payment method: {payment_method}")
        return None

    if not result.success:
        log.error(f"Payment failed: {result.error}")
        return None

    # Update database (10 lines of DB updates)
    order.status = 'completed'
    order.total = total
    order.payment_id = result.payment_id
    for item in order.items:
        product = db.query(Product).filter_by(id=item.product_id).first()
        product.stock -= item.quantity
    db.commit()

    return order


# AFTER: Extracted into focused functions
def process_order(order_id: int) -> Optional[Order]:
    """Process an order from validation through payment.

    Args:
        order_id: ID of the order to process

    Returns:
        Completed order object, or None if processing failed
    """
    order = fetch_order(order_id)
    if not order:
        return None

    if not validate_order(order):
        return None

    total = calculate_order_total(order)

    payment_result = charge_payment(order, total)
    if not payment_result:
        return None

    return finalize_order(order, total, payment_result)


def fetch_order(order_id: int) -> Optional[Order]:
    """Fetch order from database with error handling."""
    order = db.query(Order).filter_by(id=order_id).first()
    if not order:
        log.error(f"Order not found: {order_id}")
        return None
    return order


def validate_order(order: Order) -> bool:
    """Validate order has items and sufficient stock."""
    if not order.items:
        log.error(f"Empty order: {order.id}")
        return False

    for item in order.items:
        if not validate_order_item(item):
            return False

    return True


def validate_order_item(item: OrderItem) -> bool:
    """Validate a single order item has valid quantity and stock."""
    if item.quantity <= 0:
        log.error(f"Invalid quantity: {item.quantity}")
        return False

    product = db.query(Product).filter_by(id=item.product_id).first()
    if not product or product.stock < item.quantity:
        log.error(f"Insufficient stock for product: {item.product_id}")
        return False

    return True


def calculate_order_total(order: Order) -> float:
    """Calculate order total including tax and shipping."""
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * TAX_RATE
    shipping = FREE_SHIPPING_THRESHOLD if subtotal < 50 else 0.0
    return subtotal + tax + shipping


def charge_payment(order: Order, total: float) -> Optional[PaymentResult]:
    """Charge payment using order's payment method."""
    method = order.payment_method

    if method == 'credit':
        result = process_credit_card(order.card_token, total)
    elif method == 'paypal':
        result = process_paypal(order.paypal_email, total)
    else:
        log.error(f"Invalid payment method: {method}")
        return None

    if not result.success:
        log.error(f"Payment failed: {result.error}")
        return None

    return result


def finalize_order(order: Order, total: float, payment: PaymentResult) -> Order:
    """Update order and inventory after successful payment."""
    order.status = 'completed'
    order.total = total
    order.payment_id = payment.payment_id

    for item in order.items:
        deduct_inventory(item.product_id, item.quantity)

    db.commit()
    return order


def deduct_inventory(product_id: int, quantity: int):
    """Deduct quantity from product inventory."""
    product = db.query(Product).filter_by(id=product_id).first()
    product.stock -= quantity
```

**Metrics Impact:**
- Main function length: 60 lines → 12 lines (80% reduction)
- Avg function length: 60 lines → 8 lines
- Cyclomatic complexity: 15 → 3 per function
- Testability: Can now test each step independently

---

## 2. Encapsulate Global State

**Problem:** Module-level globals are mutated from scattered call sites, making state changes hard to trace and impossible to isolate in tests.

**Solution:** Move the state and the functions that mutate it into a class; module-level functions become methods operating on `self`.

```python
# BEFORE: Global state mutated from anywhere in the module
_connection = None
_request_count = 0

def connect(dsn: str) -> None:
    global _connection
    _connection = create_connection(dsn)

def run_query(sql: str) -> list:
    global _request_count
    _request_count += 1
    return _connection.execute(sql)

def stats() -> dict:
    return {"requests": _request_count}


# AFTER: State encapsulated, no globals
class QueryClient:
    """Runs queries against a connection, tracking request count."""

    def __init__(self, dsn: str) -> None:
        self._connection = create_connection(dsn)
        self._request_count = 0

    def run_query(self, sql: str) -> list:
        self._request_count += 1
        return self._connection.execute(sql)

    def stats(self) -> dict:
        return {"requests": self._request_count}
```

**Metrics Impact:**
- Global statements: 2 → 0
- Testability: Multiple independent `QueryClient` instances can now coexist in tests; no shared mutable module state to reset between them

---

## 3. Group Related Functions

**Problem:** Standalone functions that all operate on the same data (repeatedly re-fetched or re-passed as parameters) are scattered across a module with no signal that they belong together.

**Solution:** Organize them into a class by responsibility; shared data becomes constructor-injected state instead of a repeated parameter.

```python
# BEFORE: Scattered functions, each re-fetching what the last one already had
def get_user(user_id):
    return db.query(User).filter_by(id=user_id).first()

def get_recent_orders(user_id, limit=10):
    return db.query(Order).filter_by(user_id=user_id).order_by(Order.created_at.desc()).limit(limit).all()

def get_user_total_spent(user_id):
    orders = get_recent_orders(user_id)
    return sum(order.amount for order in orders)


# AFTER: Grouped by responsibility, data access isolated
class UserRepository:
    """Data access for a single user and their order history."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def get_user(self) -> User:
        return db.query(User).filter_by(id=self.user_id).first()

    def get_recent_orders(self, limit: int = 10) -> list[Order]:
        return (
            db.query(Order)
            .filter_by(user_id=self.user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_total_spent(self) -> float:
        return sum(order.amount for order in self.get_recent_orders())
```

**Metrics Impact:**
- Redundant queries: `get_recent_orders` fetched once and reused, not re-run per caller
- Cohesion: functions operating on the same `user_id` are now discoverable as one unit instead of independently named globals

---

## 4. Create Domain Models

**Problem:** Primitive dicts and tuples passed between functions carry no type information or validation; a typo in a key name fails silently at runtime.

**Solution:** Replace them with a `dataclass` (and an `Enum` for closed sets of values).

```python
# BEFORE: Primitive dict, no validation, silent typos
def create_order(items: list) -> dict:
    return {
        'items': items,
        'status': 'pending',  # or 'completed', 'cancelled' -- not enforced
        'total': sum(i['price'] * i['qty'] for i in items),
    }

def is_completed(order: dict) -> bool:
    return order['sttaus'] == 'completed'  # typo -- always False, no error


# AFTER: Domain model with an enum for the closed status set
from dataclasses import dataclass
from enum import Enum, auto


class OrderStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    CANCELLED = auto()


@dataclass
class OrderItem:
    price: float
    qty: int


@dataclass
class Order:
    items: list[OrderItem]
    status: OrderStatus = OrderStatus.PENDING

    @property
    def total(self) -> float:
        return sum(item.price * item.qty for item in self.items)

    def is_completed(self) -> bool:
        return self.status == OrderStatus.COMPLETED  # typo would be a caught AttributeError
```

**Metrics Impact:**
- Type-hint coverage: dict access replaced with typed attribute access, catchable by static analysis
- Correctness: invalid status values and misspelled field access fail at construction/attribute-access time instead of silently

---

## 5. Apply Dependency Injection

**Problem:** A function or class hard-codes its collaborators, so it can't be tested without the real database, network, or clock -- and can't be reused with a different implementation.

**Solution:** Accept the collaborator as a constructor or function parameter instead of importing/instantiating it internally.

```python
# BEFORE: Hard-coded dependency, untestable without a real DB
class OrderService:
    def get_order_total(self, order_id: int) -> float:
        conn = PostgresConnection(DATABASE_URL)  # hard-coded
        order = conn.query(f"SELECT * FROM orders WHERE id = {order_id}")
        return order.total


# AFTER: Dependency injected, testable with a fake
class OrderService:
    """Look up order totals via an injected data source."""

    def __init__(self, connection: OrderConnection) -> None:
        self._connection = connection

    def get_order_total(self, order_id: int) -> float:
        order = self._connection.get_order(order_id)
        return order.total


# Test uses a fake instead of a real Postgres connection
class FakeOrderConnection:
    def get_order(self, order_id: int) -> Order:
        return Order(id=order_id, total=42.0)


def test_get_order_total():
    service = OrderService(FakeOrderConnection())
    assert service.get_order_total(1) == 42.0
```

**Metrics Impact:**
- Testability: no real database needed to unit-test `OrderService`
- Coupling: `OrderService` now depends on the `OrderConnection` interface, not a concrete Postgres client

---

## Summary

These five patterns form this skill's structural catalog:

1. **Extract Method** -- reduce function length and cyclomatic/cognitive complexity by splitting responsibilities
2. **Encapsulate Global State** -- eliminate module-level globals in favor of instance state
3. **Group Related Functions** -- turn scattered functions sharing data into a cohesive class
4. **Create Domain Models** -- replace primitive dicts/tuples with dataclasses and enums
5. **Apply Dependency Injection** -- replace hard-coded collaborators with injected ones for testability

Apply these during Phase 3 (Execution) of the refactoring workflow, one pattern at a time, validating after each change per `references/REGRESSION_PREVENTION.md`.
