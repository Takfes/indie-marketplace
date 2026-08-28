# Python Idioms Reference

Idiom-level, behavior-preserving catalog. Structural moves (splitting a function, encapsulating
global state) live in `python-refactor` instead -- see that skill's `references/patterns.md` for
the boundary. Naming here follows `python-refactor`'s own cross-references (`references/patterns.md`
line 3, `SKILL.md` line 150/228): "Guard Clauses" and "Dictionary Techniques" below are the
idiom-level entries those two point at.

**Coverage note:** `python-refactor` also lists "dictionary dispatch" (replacing an `if`/`elif`
cascade with a `dict` mapping keys to callables) among the idioms it expects to find here.
Neither harvested source for this skill (`python-simplifier`'s prose, `affaan-m/everything-claude-code`'s
`python-patterns`) covers that specific idiom, so it's not included below -- flagged rather than
invented, since it wasn't part of this skill's harvest scope.

## Simplification Principles

1. **YAGNI** -- don't add abstractions until needed
2. **Preserve behavior** -- simplification ≠ changing functionality
3. **One change at a time** -- incremental is safer
4. **Readability over cleverness** -- clear beats "smart"
5. **Keep related code together** -- locality matters

## EAFP vs. LBYL

Python prefers exception handling over checking conditions first -- "Easier to Ask Forgiveness
than Permission" over "Look Before You Leap."

```python
# Before: LBYL -- checks first, still races with concurrent mutation
def get_value(dictionary: dict, key: str, default: object = None) -> object:
    if key in dictionary:
        return dictionary[key]
    return default

# After: EAFP -- one lookup, no race window
def get_value(dictionary: dict, key: str, default: object = None) -> object:
    try:
        return dictionary[key]
    except KeyError:
        return default
```

## Before/After Catalog

### Extract and Name

```python
# Before: complex inline condition
if user.age >= 18 and user.country in ALLOWED and not user.banned:
    ...

# After: named condition
is_eligible = user.age >= 18 and user.country in ALLOWED and not user.banned
if is_eligible:
    ...
```

### Guard Clauses (Early Returns)

```python
# Before: deep nesting
def process(data):
    if data:
        if data.valid:
            if data.ready:
                return compute(data)
    return None

# After: guard clauses
def process(data):
    if not data or not data.valid or not data.ready:
        return None
    return compute(data)
```

### Comprehensions

```python
# Before: manual loop
result = []
for item in items:
    if item.active:
        result.append(item.name)

# After: list comprehension
result = [item.name for item in items if item.active]
```

Keep comprehensions to one `for` and one `if` clause. A comprehension with nested loops or
multiple conditions reads worse than the loop it replaced -- expand it back into an explicit
`for` block (or a small generator function) once it stops fitting on one line comfortably.

### Dictionary Techniques

```python
# Before: verbose key checking
if key in d:
    value = d[key]
else:
    value = default

# After: get() with default
value = d.get(key, default)

# Before: manual grouping
groups = {}
for item in items:
    if item.category not in groups:
        groups[item.category] = []
    groups[item.category].append(item)

# After: defaultdict
from collections import defaultdict

groups = defaultdict(list)
for item in items:
    groups[item.category].append(item)
```

### Context Managers

```python
# Before: manual cleanup
f = open('file.txt')
try:
    data = f.read()
finally:
    f.close()

# After: with statement
with open('file.txt') as f:
    data = f.read()
```

## Over-Engineering Anti-Patterns

| Pattern | Problem | Solution |
|---------|---------|----------|
| Single-impl interface | Abstract class with one subclass | Merge or wait for need |
| Unnecessary factory | Factory that creates one type | Direct instantiation |
| Premature strategy | Strategy pattern with one strategy | Simple function |
| Thin wrapper | Class that just delegates | Use wrapped class directly |
| Speculative generality | Code for "future needs" | Delete it (YAGNI) |
| Deep inheritance | 4+ levels of inheritance | Composition over inheritance |

## When NOT to Simplify

- Working legacy code with no tests
- Performance-critical hot paths (measure first)
- Code that will be replaced soon
- External API constraints requiring complexity

## Type Hints

### Basic Annotations

```python
def process_user(user_id: str, data: dict[str, object], active: bool = True) -> User | None:
    """Process a user and return the updated User or None."""
    if not active:
        return None
    return User(user_id, data)
```

### Modern Syntax (3.10+)

Use built-in generics and `|` unions -- this is the project's own convention, not just a style
option:

```python
# Preferred (3.9+ for built-in generics, 3.10+ for | unions)
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Avoid unless targeting < 3.9
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
```

### Type Aliases and TypeVar

```python
from typing import TypeVar

JSON = dict[str, object] | list[object] | str | int | float | bool | None

def parse_json(data: str) -> JSON:
    return json.loads(data)

T = TypeVar('T')

def first(items: list[T]) -> T | None:
    """Return the first item or None if list is empty."""
    return items[0] if items else None
```

### Protocol-Based Duck Typing

```python
from typing import Protocol


class Renderable(Protocol):
    def render(self) -> str: ...


def render_all(items: list[Renderable]) -> str:
    """Render all items that implement the Renderable protocol."""
    return "\n".join(item.render() for item in items)
```

## Dataclasses and Named Tuples

### Dataclasses

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """User entity with automatic __init__, __repr__, and __eq__."""
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
```

### Dataclasses with Validation

```python
@dataclass
class User:
    email: str
    age: int

    def __post_init__(self) -> None:
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
        if not 0 <= self.age <= 150:
            raise ValueError(f"Invalid age: {self.age}")
```

### Named Tuples

Prefer `NamedTuple` over `dataclass` when the value is small, immutable, and never needs
mutation after construction -- it's cheaper and behaves like a tuple everywhere a tuple is
expected.

```python
from typing import NamedTuple


class Point(NamedTuple):
    """Immutable 2D point."""
    x: float
    y: float

    def distance(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
```

## Decorators

### Function Decorators

```python
import functools
import time
from collections.abc import Callable


def timer(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.perf_counter() - start:.4f}s")
        return result
    return wrapper
```

### Parameterized Decorators

```python
def repeat(times: int) -> Callable:
    """Decorator to repeat a function multiple times."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return [func(*args, **kwargs) for _ in range(times)]
        return wrapper
    return decorator


@repeat(times=3)
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

### Class-Based Decorators

```python
class CountCalls:
    """Decorator that counts how many times a function is called."""
    def __init__(self, func: Callable) -> None:
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.func(*args, **kwargs)
```

## Memory and Generator Idioms

### `__slots__` for Memory Efficiency

Worth it for classes instantiated in bulk (thousands+); adds no value for a handful of
long-lived objects.

```python
# Before: regular class uses __dict__ per instance
class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

# After: __slots__ drops the per-instance __dict__
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
```

### Generators for Large Data

```python
# Before: returns the full list in memory
def read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f]

# After: yields one line at a time
from collections.abc import Iterator


def read_lines(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()
```

## Exception Handling

### Exception Chaining

Always chain when re-raising inside an `except` block -- it preserves the original traceback
instead of hiding the real cause.

```python
def process_data(data: str) -> dict:
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse data: {data!r}") from e
```

### Custom Exception Hierarchy

```python
class AppError(Exception):
    """Base exception for all application errors."""


class ValidationError(AppError):
    """Raised when input validation fails."""


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""


def get_user(user_id: str) -> User:
    user = db.find_user(user_id)
    if not user:
        raise NotFoundError(f"User not found: {user_id}")
    return user
```

A hierarchy earns its keep once callers need to catch a whole category (`except AppError:`) or
distinguish causes without string-matching a message. For a single call site with one failure
mode, a plain `raise ValueError(...)` is simpler and doesn't need this.

## Quick Reference

| Idiom | Description |
|-------|-------------|
| EAFP | Easier to Ask Forgiveness than Permission |
| Context managers | Use `with` for resource management |
| List comprehensions | For simple transformations |
| Generators | For lazy evaluation and large datasets |
| Type hints | Annotate function signatures |
| Dataclasses | For data containers with auto-generated methods |
| `__slots__` | For memory optimization |
| f-strings | For string formatting |
| `pathlib.Path` | For path operations |
| `enumerate` | For index-element pairs in loops |
