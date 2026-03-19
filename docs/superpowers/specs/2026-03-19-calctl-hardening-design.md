# calctl Hardening Design

**Date:** 2026-03-19
**Goal:** Harden calctl with Typer CLI, proper error handling, logging, dual output formats, and tests.
**Approach:** Incremental refactor — keep flat module structure, add `errors.py` and `formatting.py`.

## File Structure (after)

```
src/calctl/
├── __init__.py
├── calendar.py      # EventKit access (refactored: exceptions, logging)
├── cli.py           # Typer CLI (replaces argparse)
├── errors.py        # Exception hierarchy (new)
├── formatting.py    # Output formatting (new)
└── py.typed
tests/
├── test_calendar.py
├── test_cli.py
└── test_formatting.py
```

## 1. Error Handling (`errors.py`)

Custom exception hierarchy rooted at `CalctlError`:

```python
class CalctlError(Exception):
    """Base exception for calctl."""

class AccessDeniedError(CalctlError):
    """Calendar access denied by macOS."""

class EventNotFoundError(CalctlError):
    """Event ID not found in the store."""

class CalendarNotFoundError(CalctlError):
    """Calendar name not found."""

class DateParseError(CalctlError):
    """Could not parse date string."""

class EventSaveError(CalctlError):
    """EventKit save or delete operation failed."""
```

`calendar.py` raises these exceptions. The CLI layer catches `CalctlError`, prints the message to stderr, and exits with code 1.

## 2. CLI Layer (`cli.py`)

Replace `argparse` with **Typer**. Each subcommand is a decorated function.

### Global options (via Typer callback)
- `--format` / `-f`: `json` | `text` (default: `text`)
- `--verbose` / `-v`: enable DEBUG logging to stderr

### Subcommands

| Command | Typer function | Key arguments |
|---------|---------------|---------------|
| `calendars` | `calendars()` | — |
| `list` | `list_events()` | `--from`, `--to`, `--calendar` |
| `search` | `search_events()` | `query` (positional), `--from`, `--to` |
| `show` | `show()` | `id` (positional) |
| `create` | `create()` | `--title` (required), `--start` (required), `--end`, `--calendar`, `--location`, `--notes`, `--all-day` |
| `edit` | `edit()` | `id` (positional), `--title`, `--start`, `--end`, `--location`, `--notes`, `--all-day` |
| `delete` | `delete()` | `id` (positional) |

### Error handling
Top-level exception handler wraps command execution:
- `CalctlError` → print message to stderr, exit code 1
- Unexpected exceptions → print generic message to stderr, log traceback at DEBUG, exit code 2

### Format propagation
Format is set via the Typer callback and stored in a module-level context or passed through. All commands call `format_output(data, format)` and print the result to stdout.

## 3. Output Formatting (`formatting.py`)

```python
class Format(str, Enum):
    json = "json"
    text = "text"
```

### `format_output(data, format, command)` dispatch:

**JSON mode:** `json.dumps(data, indent=2, default=str)` — same as current behavior.

**Text mode** (by data shape):
- **Event list** (list of event dicts): One line per event:
  `2026-03-19 10:00–11:00  Meeting Title  [Work]`
  All-day events: `2026-03-19 (all day)  Birthday  [Personal]`
- **Calendar list** (list of calendar dicts): One per line: `  Calendar Name`
- **Single event** (dict with `id`, `title`, etc.): Key-value pairs:
  ```
  Title:    Meeting
  Start:    2026-03-19T10:00:00
  End:      2026-03-19T11:00:00
  Calendar: Work
  Location: Room 42
  ```
- **Status message** (dict with `status` key): `✓ Event deleted: Meeting (2026-03-19)`

## 4. Logging

- Standard library `logging` module
- `logging.getLogger(__name__)` in each module
- `--verbose` flag configures root logger to DEBUG, output to stderr via `StreamHandler`
- Default level: WARNING (effectively silent)

### Log points in `calendar.py`:
- DEBUG: store access request, access granted/denied, date parsing, predicate creation
- DEBUG: event save/delete attempts and results
- WARNING: EventKit callback timeout approaching

## 5. `calendar.py` Refactor

Changes (behavior-preserving except for error signaling):

1. **Remove `_exit_error()`** — replaced by raising exceptions
2. **`_get_store()`** — raises `AccessDeniedError` instead of calling `_exit_error`
3. **`_ns_date()`** — raises `DateParseError` instead of calling `_exit_error`
4. **`get_event()`** — raises `EventNotFoundError` instead of returning `{"error": ...}`
5. **`create_event()`** — raises `CalendarNotFoundError` or `EventSaveError` instead of returning error dicts
6. **`edit_event()`** — raises `EventNotFoundError` or `EventSaveError`
7. **`delete_event()`** — raises `EventNotFoundError` or `EventSaveError`
8. **Add `logger = logging.getLogger(__name__)`** and DEBUG log statements at key points

All functions continue to return their current success-path types (dicts and lists).

## 6. Testing

### Dependencies (dev)
- `pytest`
- `pytest-mock`

### `tests/test_formatting.py`
- Test JSON and text output for each data shape (event list, calendar list, single event, status)
- Test edge cases: empty lists, missing optional fields

### `tests/test_cli.py`
- Use Typer's `CliRunner` to invoke commands
- Mock `calctl.calendar` functions to isolate CLI behavior from EventKit
- Test: help text, argument parsing, format flag, verbose flag, error handling (mocked exceptions)

### `tests/test_calendar.py`
- Mock `EventKit.EKEventStore` and related PyObjC objects
- Test: date parsing (`_ns_date`), event-to-dict conversion, error paths (access denied, not found, save failure)
- Test: `list_events`, `search_events`, `create_event`, `edit_event`, `delete_event` with mocked store

## 7. Dependency Changes

```toml
[project]
dependencies = [
    "pyobjc-framework-EventKit>=11.0",
    "typer>=0.15",
]

[dependency-groups]
dev = [
    "ruff>=0.15.6",
    "pytest>=8.0",
    "pytest-mock>=3.14",
]
```

## 8. Migration Notes

- The CLI interface stays the same from the user's perspective (same commands, same arguments)
- Default output changes from JSON to plain text — existing scripts should add `--format json`
- Exit codes become meaningful: 0=success, 1=calctl error, 2=unexpected error
- Typer adds `--help` on every subcommand automatically
