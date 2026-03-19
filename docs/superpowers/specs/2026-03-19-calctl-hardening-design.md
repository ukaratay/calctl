# calctl Hardening Design

**Date:** 2026-03-19
**Platform:** macOS only (requires EventKit framework via PyObjC)
**Python:** ≥3.10 (constrained by PyObjC; lowest version enabling full functionality)
**Goal:** Harden calctl with Typer CLI, proper error handling, logging, dual output formats, full EventKit coverage, strict typing/linting, and tests.
**Approach:** Incremental refactor — keep flat module structure, add `errors.py` and `formatting.py`.

## File Structure (after)

```
src/calctl/
├── __init__.py
├── calendar.py      # EventKit access (refactored: exceptions, logging, full API)
├── cli.py           # Typer CLI (replaces argparse)
├── errors.py        # Exception hierarchy (new)
├── formatting.py    # Output formatting (new)
└── py.typed
tests/
├── conftest.py      # Shared fixtures
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

class RRuleParseError(CalctlError):
    """Could not parse RRULE string."""

class AlarmParseError(CalctlError):
    """Could not parse alarm specification."""
```

`calendar.py` raises these exceptions. The CLI layer catches `CalctlError`, prints the message to stderr, and exits with code 1.

**Error output format:** Errors always go to stderr as plain text (the error message), regardless of `--format`. Stdout remains empty on errors. This keeps scripting simple: parse stdout for data, check exit code for success.

## 2. CLI Layer (`cli.py`)

Replace `argparse` with **Typer**. Each subcommand is a decorated function.

### Global options (via Typer callback)
- `--format` / `-f`: `json` | `text` (default: auto-detect — `json` when stdout is not a TTY, `text` when it is). This preserves backward compatibility for scripts/agents piping output.
- `--verbose` / `-v`: enable DEBUG logging to stderr

### Subcommands

| Command | Typer function | Key arguments |
|---------|---------------|---------------|
| `calendars` | `calendars()` | — |
| `list` | `list_events()` | `--from`, `--to`, `--calendar` |
| `search` | `search_events()` | `query` (positional), `--from`, `--to`, `--calendar` |
| `show` | `show()` | `id` (positional) |
| `create` | `create()` | `--title` (required), `--start` (required), `--end`, `--calendar`, `--location`, `--geo`, `--notes`, `--url`, `--all-day`, `--availability`, `--timezone`, `--rrule`, `--alarm` (repeatable) |
| `edit` | `edit()` | `id` (positional), `--title`, `--start`, `--end`, `--calendar`, `--location`, `--geo`, `--notes`, `--url`, `--all-day`/`--no-all-day`, `--availability`, `--timezone`, `--rrule`, `--alarm` (repeatable), `--span` |
| `delete` | `delete()` | `id` (positional), `--span` |

### Typer-specific notes

- **`--from` is a Python keyword.** Use `Annotated[str, typer.Option("--from")]` with Python parameter name `from_date`.
- **`--all-day` on `edit` is tri-state.** Use `Optional[bool] = typer.Option(None, "--all-day/--no-all-day")`. This gives three states: `None` (not provided, no change), `True` (`--all-day`), `False` (`--no-all-day`). This is an intentional improvement over argparse — users can now explicitly unset all-day status. **Note:** This adds `--no-all-day` which didn't exist before — documented in Migration Notes.
- **`--alarm` is repeatable.** Use `Optional[list[str]] = typer.Option(None, "--alarm")`. Multiple `--alarm` flags allowed. `--alarm ""` clears all alarms and **must be the sole `--alarm` value** — raise `AlarmParseError` if combined with other alarm values.
- **`--span`** defaults to `this`. Values: `this` | `future`. Only on `edit` and `delete` (not `create` — a new event has no existing series).
- **Global options** are placed on the Typer callback, so they can appear before or after the subcommand.

### Error handling
Top-level exception handler wraps command execution:
- `CalctlError` → print message to stderr, exit code 1
- Unexpected exceptions → print generic message to stderr, log traceback at DEBUG, exit code 2

### Format propagation
Format is resolved in the Typer callback (auto-detect or explicit) and stored in a module-level context variable. All commands call `format_output(data, format)` and print the result to stdout.

## 3. Output Formatting (`formatting.py`)

```python
class Format(str, Enum):
    json = "json"
    text = "text"
```

### `format_output(data, format)` dispatch:

Dispatch is by **data shape** using the `_action` discriminator key. Priority order:

1. **Action message** (dict with `"_action"` key — values: `"created"`, `"updated"`, `"deleted"`):
   - `"deleted"`: `✓ Event deleted: Meeting (2026-03-19)`
   - `"created"`: `✓ Created:` prefix line, followed by key-value event details
   - `"updated"`: `✓ Updated:` prefix line, followed by key-value event details
2. **Single event** (dict with `"id"` + `"title"` keys, no `"_action"`): Key-value pairs (see below)
3. **Event list** (list of dicts with `"id"` key): One line per event
4. **Calendar list** (list of dicts with `"name"` key, no `"id"`): One per line

`format_output` **consumes and removes** the `_action` key from the dict before serializing in **both** JSON and text modes. In JSON mode, consumers never see `_action`. In text mode, it drives the prefix line.

**JSON mode:** `json.dumps(data, indent=2, default=str)` (after stripping `_action`).

**Text mode** details:
- **Event list**: One line per event:
  `2026-03-19 10:00–11:00  Meeting Title  [Work]`
  All-day events: `2026-03-19 (all day)  Birthday  [Personal]`
  Recurring: `2026-03-19 10:00–11:00  Standup  [Work]  🔁 FREQ=WEEKLY;BYDAY=MO,WE,FR`
  Empty list: `No events found.`
- **Calendar list**: One per line: `  Calendar Name`
  Empty list: `No calendars found.`
- **Single event** (show, or body of created/updated):
  ```
  Title:        Meeting
  Start:        2026-03-19T10:00:00
  End:          2026-03-19T11:00:00
  Calendar:     Work
  Location:     Room 42
  Geo:          37.7749, -122.4194
  URL:          https://meet.example.com/123
  Availability: busy
  Status:       confirmed
  Organizer:    Jane Doe <jane@example.com>
  Attendees:    John (accepted), Alice (tentative)
  Alarms:       -15m, -1h
  Recurrence:   FREQ=WEEKLY;BYDAY=MO,WE,FR
  Timezone:     America/New_York
  Created:      2026-03-18T09:00:00
  Modified:     2026-03-18T15:30:00
  ```
  (Empty/null fields are omitted in text mode)

## 4. Logging

- Standard library `logging` module
- `logging.getLogger(__name__)` in each module
- `--verbose` flag configures root logger to DEBUG, output to stderr via `StreamHandler`
- Default level: WARNING (effectively silent)

### Log points in `calendar.py`:
- DEBUG: store access request, access granted/denied, date parsing, predicate creation
- DEBUG: event save/delete attempts and results, RRULE parsing, alarm parsing
- WARNING: EventKit callback timeout approaching

## 5. RRULE Handling (via `python-dateutil`)

Uses `python-dateutil` for RRULE parsing and serialization — no custom parser.

### RRULE string → EKRecurrenceRule (in `calendar.py`)
1. Parse RRULE string with `dateutil.rrule.rrulestr()` to get a `dateutil.rrule.rrule` object
2. Extract components (freq, interval, count, until, byweekday, bymonthday, bymonth, bysetpos, wkst)
3. Map to EventKit types: `EKRecurrenceFrequency`, `EKRecurrenceDayOfWeek`, `EKRecurrenceEnd`
4. Construct `EKRecurrenceRule` via `initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_`

### EKRecurrenceRule → RRULE string (in `calendar.py`)
1. Extract components from `EKRecurrenceRule` (frequency, interval, daysOfTheWeek, etc.)
2. Build RRULE string manually from components (straightforward key=value assembly)
3. No dateutil needed for this direction — it's simple string formatting

Raises `RRuleParseError` (wrapping dateutil exceptions) for invalid RRULE strings.

## 6. `calendar.py` — Full EventKit Coverage

### Enriched event output (`_event_to_dict`)

All fields returned by `_event_to_dict`:

```python
{
    "id": str,
    "title": str,
    "start": str,              # ISO 8601
    "end": str,                # ISO 8601
    "all_day": bool,
    "location": str,
    "geo": {"lat": float, "lng": float} | None,  # from structuredLocation
    "notes": str,
    "calendar": str,
    "url": str,
    "availability": str | None,  # "free" | "busy" | "tentative" | "unavailable" | None (not_supported)
    "status": str,             # "none" | "confirmed" | "tentative" | "canceled" (read-only)
    "organizer": {"name": str, "email": str} | None,  # read-only
    "attendees": [             # read-only
        {"name": str, "email": str, "status": str, "role": str}
    ],
    "alarms": [str],           # ["-15m", "-1h", "2026-03-20T09:00:00"]
    "rrule": str | None,       # RRULE string or null
    "timezone": str | None,    # IANA timezone name
    "is_detached": bool,       # detached from recurring series
    "created": str | None,     # ISO 8601 (read-only)
    "modified": str | None,    # ISO 8601 (read-only)
}
```

**Note on `availability`:** `EKEventAvailabilityNotSupported` maps to `None` (null in JSON, omitted in text). Only `free`, `busy`, `tentative`, `unavailable` are valid for writing.

### Writable fields on create/edit

| Field | Flag | Notes |
|-------|------|-------|
| title | `--title` | Required on create |
| start | `--start` | Required on create |
| end | `--end` | Default: +1h or same day (all-day) |
| all_day | `--all-day` / `--no-all-day` | Tri-state on edit |
| calendar | `--calendar` | Name match. On edit: moves event to new calendar |
| location | `--location` | String location. Clear with `--location ""` |
| geo | `--geo` | `lat,lng` format. Sets structuredLocation. Clear with `--geo ""` |
| notes | `--notes` | Event notes. Clear with `--notes ""` |
| url | `--url` | Event URL. Clear with `--url ""` |
| availability | `--availability` | `free` \| `busy` \| `tentative` \| `unavailable` |
| timezone | `--timezone` | IANA name (e.g., `America/New_York`). Clear with `--timezone ""` |
| rrule | `--rrule` | RRULE string. Clear with `--rrule ""` |
| alarms | `--alarm` | Repeatable. Relative: `-15m`, `-1h`, `-2d`. Absolute: ISO datetime. Clear with `--alarm ""` (must be sole value) |

**Clearing fields:** Any string field can be cleared by passing an empty string (`""`). This sets the field to `None`/empty in EventKit.

### Alarm parsing

Relative alarm format: `-<number><unit>` where unit is `m` (minutes), `h` (hours), `d` (days).
- `-15m` → `EKAlarm.alarmWithRelativeOffset_(-900)` (seconds)
- `-1h` → `EKAlarm.alarmWithRelativeOffset_(-3600)`
- `-2d` → `EKAlarm.alarmWithRelativeOffset_(-172800)`

Absolute alarm: ISO datetime string → `EKAlarm.alarmWithAbsoluteDate_(_ns_date(...))`

On edit with `--alarm`: **replaces** all existing alarms (remove all, add new ones). `--alarm ""` must be the sole `--alarm` value; raise `AlarmParseError` if combined with other alarms.

### Span handling

- `--span this` (default) → `EKSpanThisEvent`
- `--span future` → `EKSpanFutureEvents`
- Applied on `save` (edit) and `remove` (delete) calls only. Not applicable to create.

### Calendar move on edit

When `--calendar` is specified on edit:
1. Look up calendar by name (case-insensitive)
2. If not found, raise `CalendarNotFoundError`
3. Set `event.setCalendar_(matching_calendar)`
4. Save with specified span

### Structured location / geo

When `--geo lat,lng` is provided:
1. Create `EKStructuredLocation` with title from `--location` (or empty)
2. Set `geoLocation` to `CLLocation(latitude, longitude)`
3. Set on event via `setStructuredLocation_`

Reading: extract from `event.structuredLocation().geoLocation()` if present.

Requires explicit `pyobjc-framework-CoreLocation` dependency for `CLLocation`.

### Timezone handling

`--timezone` sets the event's `timeZone` property via `event.setTimeZone_(NSTimeZone.timeZoneWithName_(tz_name))`. This controls how Calendar.app displays the event time (floating vs anchored behavior).

**`--start` and `--end` are always parsed in local time.** The `--timezone` flag is metadata only — it does not affect how start/end strings are interpreted. It tells Calendar.app "this event is in timezone X" for display purposes.

### Availability mapping

```python
AVAILABILITY_MAP = {
    "busy": EventKit.EKEventAvailabilityBusy,                   # 0
    "free": EventKit.EKEventAvailabilityFree,                   # 1
    "tentative": EventKit.EKEventAvailabilityTentative,         # 2
    "unavailable": EventKit.EKEventAvailabilityUnavailable,     # 3
}

# For reading (reverse map, not_supported → None)
AVAILABILITY_REVERSE = {
    EventKit.EKEventAvailabilityNotSupported: None,
    EventKit.EKEventAvailabilityBusy: "busy",
    EventKit.EKEventAvailabilityFree: "free",
    EventKit.EKEventAvailabilityTentative: "tentative",
    EventKit.EKEventAvailabilityUnavailable: "unavailable",
}
```

### Status mapping (read-only)

```python
STATUS_MAP = {
    EventKit.EKEventStatusNone: "none",
    EventKit.EKEventStatusConfirmed: "confirmed",
    EventKit.EKEventStatusTentative: "tentative",
    EventKit.EKEventStatusCanceled: "canceled",
}
```

### Attendee/Participant extraction (read-only)

```python
def _participant_to_dict(p) -> dict:
    return {
        "name": str(p.name() or ""),
        "email": str(p.URL().resourceSpecifier()) if p.URL() else "",
        "status": PARTICIPANT_STATUS_MAP[p.participantStatus()],
        "role": PARTICIPANT_ROLE_MAP[p.participantRole()],
    }
```

### Updated function signatures

```python
def create_event(
    title: str,
    start: str,
    end: str | None = None,
    calendar: str | None = None,
    location: str | None = None,
    geo: str | None = None,          # "lat,lng" or "" to clear
    notes: str | None = None,
    url: str | None = None,
    all_day: bool = False,
    availability: str | None = None,
    timezone: str | None = None,
    rrule: str | None = None,
    alarms: list[str] | None = None,
) -> dict[str, Any]:
    ...

def edit_event(
    event_id: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    calendar: str | None = None,     # moves event to this calendar
    location: str | None = None,     # "" clears
    geo: str | None = None,          # "lat,lng" or "" to clear
    notes: str | None = None,        # "" clears
    url: str | None = None,          # "" clears
    all_day: bool | None = None,
    availability: str | None = None,
    timezone: str | None = None,     # "" clears
    rrule: str | None = None,        # "" clears
    alarms: list[str] | None = None, # [""] clears all
    span: str = "this",
) -> dict[str, Any]:
    ...

def delete_event(
    event_id: str,
    span: str = "this",
) -> dict[str, Any]:
    ...
```

### Refactored error handling

1. **Remove `_exit_error()`** — replaced by raising exceptions
2. **`_get_store()`** — raises `AccessDeniedError` instead of calling `_exit_error`
3. **`_ns_date()`** — raises `DateParseError` instead of calling `_exit_error`
4. **`get_event()`** — raises `EventNotFoundError` instead of returning `{"error": ...}`
5. **`create_event()`** — raises `CalendarNotFoundError`, `EventSaveError`, `RRuleParseError`, or `AlarmParseError`
6. **`edit_event()`** — raises `EventNotFoundError`, `EventSaveError`, `CalendarNotFoundError`, `RRuleParseError`, or `AlarmParseError`
7. **`delete_event()`** — raises `EventNotFoundError` or `EventSaveError`; returns dict with `"_action": "deleted"` key
8. **`create_event()`** — returns dict with `"_action": "created"` key
9. **`edit_event()`** — returns dict with `"_action": "updated"` key
10. **`list_events()` with non-existent `--calendar`** — continues to return empty list (filtering behavior, not lookup error)
11. **Add `logger = logging.getLogger(__name__)`** and DEBUG log statements at key points

### Default date ranges (documented)
- **`list`**: `--from` defaults to today, `--to` defaults to +7 days (set in CLI layer)
- **`search`**: `--from` defaults to −30 days, `--to` defaults to +90 days (set in `calendar.py`)

### Input validation (all in `calendar.py`)
All date range and input validation happens in `calendar.py`, before querying EventKit:

- **Date range**: if `--from` > `--to`, raise `DateParseError("Start date must be before end date")`
- **Event times**: if `--end` < `--start` on create/edit, raise `DateParseError("End time must be after start time")`
- **All-day with datetime**: all-day events accept both `YYYY-MM-DD` and `YYYY-MM-DDTHH:MM:SS`; the time portion is ignored
- **Geo format**: must be `lat,lng` with valid float values, raise `CalctlError` otherwise
- **Availability**: must be one of `free`, `busy`, `tentative`, `unavailable`

## 7. Testing

### Dependencies (dev)
- `pytest`
- `pytest-mock`

### Platform handling
- `calendar.py` tests are marked with `@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")` for CI compatibility
- `formatting.py` and CLI tests (with mocked calendar functions) run on all platforms

### Static analysis
- All code must pass `ruff check` and `ruff format --check` with the strict config (§8)
- All pure-Python modules (`errors.py`, `formatting.py`, `cli.py`) must pass `pyright` strict mode with zero errors
- `calendar.py` must pass pyright with warnings (not errors) for PyObjC dynamic types

### `tests/test_formatting.py`
- Test JSON and text output for each data shape (event list, calendar list, single event, action messages)
- Test `_action` key stripping in both JSON and text modes
- Test edge cases: empty lists, missing optional fields, events with attendees/alarms/rrule
- Test `availability: null` (not_supported) handling

### `tests/test_cli.py`
- Use Typer's `CliRunner` to invoke commands
- Mock `calctl.calendar` functions to isolate CLI behavior from EventKit
- Test: help text, argument parsing, format flag, verbose flag, error handling (mocked exceptions)
- Test: TTY auto-detection logic for default format
- Test: repeatable --alarm flag, --span flag, --rrule flag, --geo flag
- Test: --alarm "" rejects combination with other alarms
- Test: --span not available on create

### `tests/test_calendar.py`
- Mock `EventKit.EKEventStore` and related PyObjC objects
- Test: date parsing (`_ns_date`), event-to-dict conversion (all fields), error paths
- Test: alarm parsing (relative and absolute), structured location, availability mapping
- Test: RRULE ↔ EKRecurrenceRule conversion (all FREQ types, BYDAY, BYMONTHDAY, complex patterns, round-trip, error cases)
- Test: `list_events`, `search_events`, `create_event`, `edit_event`, `delete_event` with mocked store
- Test: input validation (date range, end < start, geo format)
- Test: calendar move on edit, span handling
- Test: clearing fields with empty strings

## 8. Project Configuration & Dependencies

### `pyproject.toml`

```toml
[project]
name = "calctl"
version = "0.1.0"
description = "macOS Calendar CLI using EventKit"
requires-python = ">=3.10"
dependencies = [
    "pyobjc-framework-EventKit>=11.0",
    "pyobjc-framework-CoreLocation>=11.0",
    "python-dateutil>=2.9",
    "typer>=0.15",
]

[project.scripts]
calctl = "calctl.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "ruff>=0.15.6",
    "pyright>=1.1",
    "pytest>=8.0",
    "pytest-mock>=3.14",
]
```

### Ruff (`ruff.toml` or `[tool.ruff]` in pyproject.toml)

Strict defaults with all safety-focused rules enabled:

```toml
[tool.ruff]
target-version = "py310"
line-length = 88

[tool.ruff.lint]
select = [
    "ALL",       # Start with everything
]
ignore = [
    "D",         # pydocstyle — skip for now (add later)
    "COM812",    # trailing comma (conflicts with formatter)
    "ISC001",    # implicit string concat (conflicts with formatter)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
    "S101",      # assert in tests is fine
    "ANN",       # annotations not required in tests
    "PLR2004",   # magic values in tests are fine
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Pyright

Strict mode for full type safety:

```toml
[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "strict"
reportMissingTypeStubs = "warning"        # PyObjC lacks stubs
reportUnknownMemberType = "warning"       # PyObjC dynamic attributes
reportUnknownArgumentType = "warning"     # PyObjC callback types
reportUnknownVariableType = "warning"     # PyObjC return types
reportAttributeAccessIssue = "warning"    # PyObjC dynamic methods
```

**Note on PyObjC and Pyright:** PyObjC uses dynamic Objective-C bridging — most EventKit types have no Python type stubs. The pyright config relaxes `reportMissing*`/`reportUnknown*` rules to `warning` (not `error`) to avoid false positives on PyObjC calls. All pure-Python code (errors, formatting, rrule, CLI) must pass strict checks with zero errors.

### CI / Developer Workflow

All checks must pass before commit:
```bash
uv run ruff check .                # Lint
uv run ruff format --check .       # Format check
uv run pyright                     # Type check
uv run pytest                      # Tests
```

## 9. Platform & Compatibility

- **macOS only.** calctl depends on Apple's EventKit framework via PyObjC. It will not install or run on Linux/Windows.
- `pyproject.toml` does not add platform classifiers or markers — PyObjC itself will fail to install on non-macOS platforms, which is sufficient.
- All test files for `calendar.py` use `@pytest.mark.skipif(sys.platform != "darwin")` for safety, though in practice tests will only run on macOS.
- `formatting.py`, `rrule.py`, `errors.py`, and CLI integration tests (with mocked calendar) are pure Python and technically cross-platform.


