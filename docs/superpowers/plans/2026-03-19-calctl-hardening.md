# calctl Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden calctl with Typer CLI, proper error handling, logging, dual output formats, full EventKit coverage, strict typing/linting, tests, and PyPI readiness.

**Architecture:** Incremental refactor of existing flat module structure. Add `errors.py` (exception hierarchy), `formatting.py` (output formatting with Format enum), update `calendar.py` (full EventKit coverage, exceptions, logging), rewrite `cli.py` (Typer replacing argparse). All pure-Python modules pass pyright strict; `calendar.py` allows PyObjC warnings.

**Tech Stack:** Python ≥3.10, Typer, PyObjC (EventKit + CoreLocation), python-dateutil, pytest, ruff (ALL rules), pyright (strict)

**Spec:** `docs/superpowers/specs/2026-03-19-calctl-hardening-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pyproject.toml` | Modify | Add deps, classifiers, ruff/pyright config, update Python version |
| `LICENSE` | Create | MIT license |
| `README.md` | Rewrite | Full docs for PyPI/GitHub |
| `src/calctl/__init__.py` | Modify | Update docstring, expose version |
| `src/calctl/errors.py` | Create | Exception hierarchy |
| `src/calctl/formatting.py` | Create | Format enum, output formatting dispatch |
| `src/calctl/calendar.py` | Rewrite | Full EventKit coverage, exceptions, logging, RRULE adapter |
| `src/calctl/cli.py` | Rewrite | Typer CLI with all subcommands |
| `tests/conftest.py` | Create | Shared fixtures |
| `tests/test_formatting.py` | Create | Formatting tests |
| `tests/test_cli.py` | Create | CLI integration tests |
| `tests/test_calendar.py` | Create | Calendar layer tests |

---

### Task 1: Project Configuration

Update `pyproject.toml` with all dependencies, tool configs, classifiers. Add LICENSE. Install deps.

**Files:**
- Modify: `pyproject.toml`
- Create: `LICENSE`

- [ ] **Step 1: Update pyproject.toml**

Replace the entire `pyproject.toml` with the target configuration:

```toml
[project]
name = "calctl"
version = "0.1.0"
description = "macOS Calendar CLI using EventKit"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    { name = "Umur Karatay", email = "umur@karatay.com" },
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business :: Scheduling",
    "Typing :: Typed",
]
dependencies = [
    "pyobjc-framework-EventKit>=11.0",
    "pyobjc-framework-CoreLocation>=11.0",
    "python-dateutil>=2.9",
    "typer>=0.15",
]

[project.scripts]
calctl = "calctl.cli:main"

[project.urls]
Homepage = "https://github.com/ukaratay/calctl"
Repository = "https://github.com/ukaratay/calctl"
Issues = "https://github.com/ukaratay/calctl/issues"

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

[tool.ruff]
target-version = "py310"
line-length = 88

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D",         # pydocstyle — skip for now
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

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "strict"
reportMissingTypeStubs = "warning"
reportUnknownMemberType = "warning"
reportUnknownArgumentType = "warning"
reportUnknownVariableType = "warning"
reportAttributeAccessIssue = "warning"
```

- [ ] **Step 2: Create LICENSE file**

Create `LICENSE` with MIT license, copyright 2026 Umur Karatay.

- [ ] **Step 3: Install dependencies**

Run: `uv sync --all-groups`
Expected: All deps install successfully including typer, python-dateutil, pyobjc-framework-CoreLocation, pyright, pytest, pytest-mock.

- [ ] **Step 4: Verify tools work**

Run:
```bash
uv run ruff check . 2>&1 | head -5
uv run pyright --version
uv run pytest --version
```
Expected: All tools available.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml LICENSE uv.lock
git commit -m "chore: update project config — deps, ruff ALL, pyright strict, MIT license"
```

---

### Task 2: Error Handling (`errors.py`)

Create the exception hierarchy. This is a dependency for all other modules.

**Files:**
- Create: `src/calctl/errors.py`

- [ ] **Step 1: Create errors.py**

```python
"""calctl exception hierarchy."""

from __future__ import annotations


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

- [ ] **Step 2: Verify with ruff and pyright**

Run:
```bash
uv run ruff check src/calctl/errors.py
uv run ruff format --check src/calctl/errors.py
uv run pyright src/calctl/errors.py
```
Expected: All pass clean.

- [ ] **Step 3: Commit**

```bash
git add src/calctl/errors.py
git commit -m "feat: add exception hierarchy (errors.py)"
```

---

### Task 3: Output Formatting (`formatting.py`)

Create the Format enum and `format_output` dispatch function. No EventKit dependency — pure Python.

**Files:**
- Create: `src/calctl/formatting.py`
- Create: `tests/test_formatting.py`

- [ ] **Step 1: Write test_formatting.py**

```python
"""Tests for calctl.formatting."""

from __future__ import annotations

import json

from calctl.formatting import Format, format_output


class TestJsonFormat:
    def test_event_list(self):
        events = [
            {"id": "1", "title": "Meeting", "start": "2026-03-19T10:00:00",
             "end": "2026-03-19T11:00:00", "all_day": False, "calendar": "Work",
             "location": "", "notes": "", "url": "", "availability": "busy",
             "status": "confirmed", "organizer": None, "attendees": [],
             "alarms": [], "rrule": None, "timezone": None, "is_detached": False,
             "geo": None, "created": None, "modified": None}
        ]
        result = json.loads(format_output(events, Format.json))
        assert len(result) == 1
        assert result[0]["title"] == "Meeting"

    def test_action_key_stripped_in_json(self):
        data = {"id": "1", "title": "Meeting", "_action": "created",
                "start": "2026-03-19T10:00:00", "end": "2026-03-19T11:00:00",
                "all_day": False, "calendar": "Work", "location": "",
                "notes": "", "url": "", "availability": None, "status": "none",
                "organizer": None, "attendees": [], "alarms": [], "rrule": None,
                "timezone": None, "is_detached": False, "geo": None,
                "created": None, "modified": None}
        result = json.loads(format_output(data, Format.json))
        assert "_action" not in result
        assert result["title"] == "Meeting"

    def test_calendar_list(self):
        cals = [{"name": "Work", "id": "cal-1"}, {"name": "Personal", "id": "cal-2"}]
        result = json.loads(format_output(cals, Format.json))
        assert len(result) == 2

    def test_empty_list(self):
        result = json.loads(format_output([], Format.json))
        assert result == []


class TestTextFormat:
    def test_event_list_single(self):
        events = [
            {"id": "1", "title": "Meeting", "start": "2026-03-19T10:00:00",
             "end": "2026-03-19T11:00:00", "all_day": False, "calendar": "Work",
             "location": "", "notes": "", "url": "", "availability": "busy",
             "status": "confirmed", "organizer": None, "attendees": [],
             "alarms": [], "rrule": None, "timezone": None, "is_detached": False,
             "geo": None, "created": None, "modified": None}
        ]
        result = format_output(events, Format.text)
        assert "Meeting" in result
        assert "Work" in result
        assert "10:00" in result

    def test_event_list_all_day(self):
        events = [
            {"id": "1", "title": "Birthday", "start": "2026-03-19T00:00:00",
             "end": "2026-03-20T00:00:00", "all_day": True, "calendar": "Personal",
             "location": "", "notes": "", "url": "", "availability": None,
             "status": "none", "organizer": None, "attendees": [],
             "alarms": [], "rrule": None, "timezone": None, "is_detached": False,
             "geo": None, "created": None, "modified": None}
        ]
        result = format_output(events, Format.text)
        assert "all day" in result
        assert "Birthday" in result

    def test_event_list_recurring(self):
        events = [
            {"id": "1", "title": "Standup", "start": "2026-03-19T09:00:00",
             "end": "2026-03-19T09:15:00", "all_day": False, "calendar": "Work",
             "location": "", "notes": "", "url": "", "availability": None,
             "status": "none", "organizer": None, "attendees": [],
             "alarms": [], "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
             "timezone": None, "is_detached": False,
             "geo": None, "created": None, "modified": None}
        ]
        result = format_output(events, Format.text)
        assert "🔁" in result
        assert "FREQ=WEEKLY" in result

    def test_empty_event_list(self):
        assert format_output([], Format.text) == "No events found."

    def test_calendar_list(self):
        cals = [{"name": "Work"}, {"name": "Personal"}]
        result = format_output(cals, Format.text)
        assert "Work" in result
        assert "Personal" in result

    def test_empty_calendar_list(self):
        # Empty list with no "id" hint — defaults to event list message
        # Calendar list is identified by having dicts with "name" but no "id"
        # But empty list can't be distinguished, so it defaults to events
        assert "No" in format_output([], Format.text)

    def test_single_event(self):
        event = {"id": "1", "title": "Meeting", "start": "2026-03-19T10:00:00",
                 "end": "2026-03-19T11:00:00", "all_day": False, "calendar": "Work",
                 "location": "Room 42", "notes": "Discuss Q2", "url": "",
                 "availability": "busy", "status": "confirmed",
                 "organizer": {"name": "Jane", "email": "jane@co.com"},
                 "attendees": [{"name": "John", "email": "john@co.com",
                                "status": "accepted", "role": "required"}],
                 "alarms": ["-15m"], "rrule": None, "timezone": "America/New_York",
                 "is_detached": False, "geo": {"lat": 37.77, "lng": -122.42},
                 "created": "2026-03-18T09:00:00", "modified": "2026-03-18T15:30:00"}
        result = format_output(event, Format.text)
        assert "Title:" in result
        assert "Meeting" in result
        assert "Room 42" in result
        assert "37.77" in result
        assert "Jane" in result
        assert "John (accepted)" in result
        assert "-15m" in result
        assert "America/New_York" in result

    def test_single_event_omits_empty_fields(self):
        event = {"id": "1", "title": "Simple", "start": "2026-03-19T10:00:00",
                 "end": "2026-03-19T11:00:00", "all_day": False, "calendar": "Work",
                 "location": "", "notes": "", "url": "", "availability": None,
                 "status": "none", "organizer": None, "attendees": [],
                 "alarms": [], "rrule": None, "timezone": None,
                 "is_detached": False, "geo": None,
                 "created": None, "modified": None}
        result = format_output(event, Format.text)
        assert "Location:" not in result
        assert "Organizer:" not in result
        assert "Alarms:" not in result

    def test_action_created(self):
        data = {"id": "1", "title": "New Event", "_action": "created",
                "start": "2026-03-19T10:00:00", "end": "2026-03-19T11:00:00",
                "all_day": False, "calendar": "Work", "location": "",
                "notes": "", "url": "", "availability": None, "status": "none",
                "organizer": None, "attendees": [], "alarms": [], "rrule": None,
                "timezone": None, "is_detached": False, "geo": None,
                "created": None, "modified": None}
        result = format_output(data, Format.text)
        assert "✓ Created:" in result
        assert "New Event" in result

    def test_action_deleted(self):
        data = {"id": "1", "title": "Old Event", "_action": "deleted",
                "start": "2026-03-19T10:00:00", "end": "2026-03-19T11:00:00",
                "all_day": False, "calendar": "Work", "location": "",
                "notes": "", "url": "", "availability": None, "status": "none",
                "organizer": None, "attendees": [], "alarms": [], "rrule": None,
                "timezone": None, "is_detached": False, "geo": None,
                "created": None, "modified": None}
        result = format_output(data, Format.text)
        assert "✓ Event deleted:" in result
        assert "Old Event" in result

    def test_action_updated(self):
        data = {"id": "1", "title": "Changed", "_action": "updated",
                "start": "2026-03-19T10:00:00", "end": "2026-03-19T11:00:00",
                "all_day": False, "calendar": "Work", "location": "",
                "notes": "", "url": "", "availability": None, "status": "none",
                "organizer": None, "attendees": [], "alarms": [], "rrule": None,
                "timezone": None, "is_detached": False, "geo": None,
                "created": None, "modified": None}
        result = format_output(data, Format.text)
        assert "✓ Updated:" in result
        assert "Changed" in result

    def test_availability_null_omitted(self):
        event = {"id": "1", "title": "X", "start": "2026-03-19T10:00:00",
                 "end": "2026-03-19T11:00:00", "all_day": False, "calendar": "W",
                 "location": "", "notes": "", "url": "", "availability": None,
                 "status": "none", "organizer": None, "attendees": [],
                 "alarms": [], "rrule": None, "timezone": None,
                 "is_detached": False, "geo": None,
                 "created": None, "modified": None}
        result = format_output(event, Format.text)
        assert "Availability:" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: ImportError — `calctl.formatting` does not exist yet.

- [ ] **Step 3: Implement formatting.py**

Create `src/calctl/formatting.py`:

```python
"""Output formatting for calctl."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class Format(str, Enum):
    """Output format options."""

    json = "json"
    text = "text"


def format_output(data: Any, fmt: Format) -> str:  # noqa: ANN401
    """Format data for output. Dispatches by data shape and format."""
    if fmt == Format.json:
        return _format_json(data)
    return _format_text(data)


def _format_json(data: Any) -> str:  # noqa: ANN401
    """Format data as JSON. Strips _action key if present."""
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if k != "_action"}
    return json.dumps(data, indent=2, default=str)


def _format_text(data: Any) -> str:  # noqa: ANN401
    """Format data as human-readable text. Dispatches by shape."""
    # Dict with _action key → action message
    if isinstance(data, dict) and "_action" in data:
        return _format_action(data)

    # Dict with id + title → single event
    if isinstance(data, dict) and "id" in data and "title" in data:
        return _format_single_event(data)

    # List
    if isinstance(data, list):
        if not data:
            return "No events found."
        first = data[0]
        if isinstance(first, dict) and "name" in first and "id" not in first:
            return _format_calendar_list(data)
        return _format_event_list(data)

    return str(data)


def _format_event_list(events: list[dict[str, Any]]) -> str:
    """Format a list of events, one per line."""
    lines: list[str] = []
    for e in events:
        if e.get("all_day"):
            date_part = f"{e['start'][:10]} (all day)"
        else:
            start_time = e["start"][11:16]
            end_time = e["end"][11:16]
            date_part = f"{e['start'][:10]} {start_time}\u2013{end_time}"

        line = f"{date_part}  {e['title']}  [{e['calendar']}]"

        if e.get("rrule"):
            line += f"  🔁 {e['rrule']}"

        lines.append(line)
    return "\n".join(lines)


def _format_calendar_list(calendars: list[dict[str, Any]]) -> str:
    """Format a list of calendars."""
    if not calendars:
        return "No calendars found."
    return "\n".join(f"  {c['name']}" for c in calendars)


def _format_single_event(event: dict[str, Any], prefix: str = "") -> str:
    """Format a single event as key-value pairs."""
    lines: list[str] = []
    if prefix:
        lines.append(prefix)

    # Always-shown fields
    lines.append(f"{'Title:':<14}{event['title']}")
    lines.append(f"{'Start:':<14}{event['start']}")
    lines.append(f"{'End:':<14}{event['end']}")

    if event.get("all_day"):
        lines.append(f"{'All Day:':<14}yes")

    lines.append(f"{'Calendar:':<14}{event['calendar']}")

    # Optional fields — only shown if non-empty
    if event.get("location"):
        lines.append(f"{'Location:':<14}{event['location']}")

    geo = event.get("geo")
    if geo:
        lines.append(f"{'Geo:':<14}{geo['lat']}, {geo['lng']}")

    if event.get("url"):
        lines.append(f"{'URL:':<14}{event['url']}")

    if event.get("availability"):
        lines.append(f"{'Availability:':<14}{event['availability']}")

    status = event.get("status")
    if status and status != "none":
        lines.append(f"{'Status:':<14}{status}")

    organizer = event.get("organizer")
    if organizer:
        org_str = organizer["name"]
        if organizer.get("email"):
            org_str += f" <{organizer['email']}>"
        lines.append(f"{'Organizer:':<14}{org_str}")

    attendees = event.get("attendees")
    if attendees:
        parts = [f"{a['name']} ({a['status']})" for a in attendees]
        lines.append(f"{'Attendees:':<14}{', '.join(parts)}")

    alarms = event.get("alarms")
    if alarms:
        lines.append(f"{'Alarms:':<14}{', '.join(alarms)}")

    if event.get("rrule"):
        lines.append(f"{'Recurrence:':<14}{event['rrule']}")

    if event.get("timezone"):
        lines.append(f"{'Timezone:':<14}{event['timezone']}")

    if event.get("created"):
        lines.append(f"{'Created:':<14}{event['created']}")

    if event.get("modified"):
        lines.append(f"{'Modified:':<14}{event['modified']}")

    return "\n".join(lines)


def _format_action(data: dict[str, Any]) -> str:
    """Format an action result (created/updated/deleted)."""
    action = data.pop("_action", "")
    start_date = data.get("start", "")[:10]

    if action == "deleted":
        return f"✓ Event deleted: {data['title']} ({start_date})"

    prefix_map = {"created": "✓ Created:", "updated": "✓ Updated:"}
    prefix = prefix_map.get(action, f"✓ {action}:")
    return _format_single_event(data, prefix=prefix)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: All tests pass.

- [ ] **Step 5: Run ruff and pyright**

Run:
```bash
uv run ruff check src/calctl/formatting.py tests/test_formatting.py
uv run ruff format --check src/calctl/formatting.py tests/test_formatting.py
uv run pyright src/calctl/formatting.py
```
Expected: All pass. Fix any issues.

- [ ] **Step 6: Commit**

```bash
git add src/calctl/formatting.py tests/test_formatting.py
git commit -m "feat: add output formatting (formatting.py) with tests"
```

---

### Task 4: Calendar Layer Rewrite (`calendar.py`)

Rewrite `calendar.py` with full EventKit coverage, exception-based error handling, logging, RRULE adapter via python-dateutil.

This is the largest task. The file interacts with PyObjC so tests require mocking.

**Files:**
- Rewrite: `src/calctl/calendar.py`
- Create: `tests/conftest.py`
- Create: `tests/test_calendar.py`

- [ ] **Step 1: Create tests/conftest.py with shared fixtures**

```python
"""Shared test fixtures for calctl."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_eventkit(monkeypatch):
    """Mock EventKit and Foundation modules for testing."""
    mock_ek = MagicMock()
    mock_foundation = MagicMock()
    mock_corelocation = MagicMock()

    # EKEntityTypeEvent constant
    mock_ek.EKEntityTypeEvent = 0

    # EKSpan constants
    mock_ek.EKSpanThisEvent = 0
    mock_ek.EKSpanFutureEvents = 1

    # Availability constants
    mock_ek.EKEventAvailabilityNotSupported = -1
    mock_ek.EKEventAvailabilityBusy = 0
    mock_ek.EKEventAvailabilityFree = 1
    mock_ek.EKEventAvailabilityTentative = 2
    mock_ek.EKEventAvailabilityUnavailable = 3

    # Status constants
    mock_ek.EKEventStatusNone = 0
    mock_ek.EKEventStatusConfirmed = 1
    mock_ek.EKEventStatusTentative = 2
    mock_ek.EKEventStatusCanceled = 3

    # Recurrence frequency constants
    mock_ek.EKRecurrenceFrequencyDaily = 0
    mock_ek.EKRecurrenceFrequencyWeekly = 1
    mock_ek.EKRecurrenceFrequencyMonthly = 2
    mock_ek.EKRecurrenceFrequencyYearly = 3

    monkeypatch.setitem(sys.modules, "EventKit", mock_ek)
    monkeypatch.setitem(sys.modules, "Foundation", mock_foundation)
    monkeypatch.setitem(sys.modules, "CoreLocation", mock_corelocation)

    return {"EventKit": mock_ek, "Foundation": mock_foundation,
            "CoreLocation": mock_corelocation}
```

- [ ] **Step 2: Write test_calendar.py — core tests**

Create `tests/test_calendar.py` with tests for:
- Date parsing (`_ns_date`) — valid dates, invalid dates raise `DateParseError`
- Alarm parsing — relative (`-15m`, `-1h`, `-2d`) and absolute, invalid raises `AlarmParseError`
- `_event_to_dict` — all fields extracted correctly
- `list_calendars` — returns list of calendar dicts
- `list_events` — with date range, with calendar filter, empty result
- `search_events` — matches title/notes/location, with calendar filter
- `get_event` — found and not found (raises `EventNotFoundError`)
- `create_event` — success with `_action: created`, calendar not found, save error
- `edit_event` — success with `_action: updated`, not found, calendar move, span
- `delete_event` — success with `_action: deleted`, not found, span
- Date validation — from > to, end < start
- Geo parsing — valid, invalid
- RRULE round-trip — parse and format

This is a large test file. Write the test structure with `pytest.mark.skipif(sys.platform != "darwin")` on tests that need real EventKit modules, and use `mock_eventkit` fixture for unit tests.

Since the tests are extensive, write them in groups as you implement each piece of calendar.py.

- [ ] **Step 3: Rewrite calendar.py**

Rewrite `src/calctl/calendar.py` with the full implementation per spec §5 and §6. Key changes from current code:

1. Import `logging`, create `logger = logging.getLogger(__name__)`
2. Import from `calctl.errors` all exceptions
3. Replace `_exit_error()` with exception raises
4. Replace `{"error": ...}` returns with exception raises
5. Add all new fields to `_event_to_dict` (availability, status, organizer, attendees, alarms, rrule, timezone, geo, is_detached, created, modified)
6. Add `_participant_to_dict`, `_format_alarm`, `_parse_alarm`, `_parse_geo`
7. Add RRULE adapter functions: `_rrule_to_ek` (using dateutil), `_ek_to_rrule`
8. Update `create_event` signature with all new params (geo, url, availability, timezone, rrule, alarms)
9. Update `edit_event` signature with all new params + calendar move + span
10. Update `delete_event` signature with span
11. Add `_action` key to return dicts (created/updated/deleted)
12. Add date range validation
13. Add DEBUG logging at key points
14. Add `search_events` calendar filter parameter

The full implementation should be ~400-500 lines. Follow the spec's function signatures exactly.

**Reference:** Spec §5 (RRULE handling) and §6 (full EventKit coverage) contain the complete function signatures, mapping tables, and validation rules needed for this implementation.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: All tests pass.

- [ ] **Step 5: Run ruff and pyright**

Run:
```bash
uv run ruff check src/calctl/calendar.py tests/test_calendar.py tests/conftest.py
uv run ruff format --check src/calctl/calendar.py tests/test_calendar.py tests/conftest.py
uv run pyright src/calctl/calendar.py
```
Expected: ruff clean, pyright may show warnings (not errors) for PyObjC types.

- [ ] **Step 6: Commit**

```bash
git add src/calctl/calendar.py tests/conftest.py tests/test_calendar.py
git commit -m "feat: rewrite calendar.py — full EventKit coverage, exceptions, logging"
```

---

### Task 5: CLI Layer Rewrite (`cli.py`)

Replace argparse with Typer. Wire up all subcommands, global options, error handling.

**Files:**
- Rewrite: `src/calctl/cli.py`
- Modify: `src/calctl/__init__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Update __init__.py**

```python
"""calctl — macOS Calendar CLI using EventKit."""

from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 2: Write test_cli.py**

Create `tests/test_cli.py` with tests using Typer's `CliRunner`:

- `test_help` — `calctl --help` shows usage
- `test_version` — (if we add --version)
- `test_calendars` — mocks `calctl.calendar.list_calendars`, verifies JSON output
- `test_list_default` — mocks `calctl.calendar.list_events`, verifies default args
- `test_list_with_calendar` — `--calendar Work`
- `test_list_json_format` — `--format json`
- `test_list_text_format` — `--format text`
- `test_show` — mocks `get_event`
- `test_create` — mocks `create_event`, verifies all args passed
- `test_edit` — mocks `edit_event`, verifies args including `--span`
- `test_delete` — mocks `delete_event`
- `test_error_handling` — mock raises `CalctlError`, verify stderr + exit code 1
- `test_unexpected_error` — mock raises `RuntimeError`, verify exit code 2
- `test_alarm_repeatable` — `--alarm -15m --alarm -1h`
- `test_alarm_empty_rejects_combination` — `--alarm "" --alarm -15m` errors
- `test_verbose_flag` — `--verbose` enables logging
- `test_search_with_calendar` — `search --calendar Work`

All tests mock `calctl.calendar` functions to avoid EventKit dependency.

**Note on error handling tests:** `CliRunner` invokes `app()` directly, bypassing the `run()` wrapper. For error handling tests (`CalctlError` → exit 1, unexpected → exit 2), either invoke `run()` directly or use `CliRunner` with `catch_exceptions=False` and assert on Typer's error handling. The recommended approach is to test `run()` directly for error code tests.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: Failures — `cli.py` still has argparse.

- [ ] **Step 4: Rewrite cli.py with Typer**

```python
"""calctl — macOS Calendar CLI."""

from __future__ import annotations

import logging
import sys
from typing import Annotated, Optional

import typer

from calctl.calendar import (
    create_event,
    delete_event,
    edit_event,
    get_event,
    list_calendars,
    list_events,
    search_events,
)
from calctl.errors import AlarmParseError, CalctlError
from calctl.formatting import Format, format_output

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="macOS Calendar CLI using EventKit",
    no_args_is_help=True,
)

# Module-level state for global options
_format: Format = Format.text


def _detect_format() -> Format:
    """Auto-detect format: JSON for pipes, text for TTY."""
    if sys.stdout.isatty():
        return Format.text
    return Format.json


def _output(data: object) -> None:
    """Format and print data to stdout."""
    print(format_output(data, _format))


@app.callback()
def main(
    fmt: Annotated[
        Optional[Format],
        typer.Option("--format", "-f", help="Output format"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging"),
    ] = False,
) -> None:
    """macOS Calendar CLI using EventKit."""
    global _format  # noqa: PLW0603
    _format = fmt if fmt is not None else _detect_format()

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stderr,
            format="%(name)s %(levelname)s: %(message)s",
        )


@app.command()
def calendars() -> None:
    """List all calendars."""
    _output(list_calendars())


@app.command("list")
def list_cmd(
    from_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Start date (YYYY-MM-DD, default: today)"),
    ] = None,
    to_date: Annotated[
        Optional[str],
        typer.Option("--to", help="End date (YYYY-MM-DD, default: +7 days)"),
    ] = None,
    calendar: Annotated[
        Optional[str],
        typer.Option(help="Filter by calendar name"),
    ] = None,
) -> None:
    """List events in a date range."""
    from datetime import datetime, timedelta

    if from_date is None:
        from_date = datetime.now().strftime("%Y-%m-%d")
    if to_date is None:
        to_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    _output(list_events(from_date, to_date, calendar))


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    from_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Start date"),
    ] = None,
    to_date: Annotated[
        Optional[str],
        typer.Option("--to", help="End date"),
    ] = None,
    calendar: Annotated[
        Optional[str],
        typer.Option(help="Filter by calendar name"),
    ] = None,
) -> None:
    """Search events by keyword."""
    _output(search_events(query, from_date, to_date, calendar))


@app.command()
def show(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
) -> None:
    """Show event details."""
    _output(get_event(event_id))


@app.command()
def create(
    title: Annotated[str, typer.Option(help="Event title")],
    start: Annotated[str, typer.Option(help="Start (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")],
    end: Annotated[Optional[str], typer.Option(help="End datetime")] = None,
    calendar: Annotated[Optional[str], typer.Option(help="Calendar name")] = None,
    location: Annotated[Optional[str], typer.Option(help="Location")] = None,
    geo: Annotated[Optional[str], typer.Option(help="Geo coordinates (lat,lng)")] = None,
    notes: Annotated[Optional[str], typer.Option(help="Notes")] = None,
    url: Annotated[Optional[str], typer.Option(help="Event URL")] = None,
    all_day: Annotated[bool, typer.Option("--all-day", help="All-day event")] = False,
    availability: Annotated[Optional[str], typer.Option(help="free|busy|tentative|unavailable")] = None,
    timezone: Annotated[Optional[str], typer.Option(help="IANA timezone")] = None,
    rrule: Annotated[Optional[str], typer.Option(help="RRULE string")] = None,
    alarm: Annotated[Optional[list[str]], typer.Option(help="Alarm (-15m, -1h, or datetime)")] = None,
) -> None:
    """Create a calendar event."""
    alarms = _validate_alarms(alarm)
    _output(create_event(
        title=title, start=start, end=end, calendar=calendar,
        location=location, geo=geo, notes=notes, url=url,
        all_day=all_day, availability=availability, timezone=timezone,
        rrule=rrule, alarms=alarms,
    ))


@app.command()
def edit(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    title: Annotated[Optional[str], typer.Option(help="Event title")] = None,
    start: Annotated[Optional[str], typer.Option(help="Start datetime")] = None,
    end: Annotated[Optional[str], typer.Option(help="End datetime")] = None,
    calendar: Annotated[Optional[str], typer.Option(help="Calendar name")] = None,
    location: Annotated[Optional[str], typer.Option(help="Location")] = None,
    geo: Annotated[Optional[str], typer.Option(help="Geo (lat,lng)")] = None,
    notes: Annotated[Optional[str], typer.Option(help="Notes")] = None,
    url: Annotated[Optional[str], typer.Option(help="Event URL")] = None,
    all_day: Annotated[Optional[bool], typer.Option("--all-day/--no-all-day", help="All-day event")] = None,
    availability: Annotated[Optional[str], typer.Option(help="free|busy|tentative|unavailable")] = None,
    timezone: Annotated[Optional[str], typer.Option(help="IANA timezone")] = None,
    rrule: Annotated[Optional[str], typer.Option(help="RRULE string")] = None,
    alarm: Annotated[Optional[list[str]], typer.Option(help="Alarm")] = None,
    span: Annotated[str, typer.Option(help="this|future")] = "this",
) -> None:
    """Edit an existing event."""
    alarms = _validate_alarms(alarm)
    _output(edit_event(
        event_id=event_id, title=title, start=start, end=end,
        calendar=calendar, location=location, geo=geo, notes=notes,
        url=url, all_day=all_day, availability=availability,
        timezone=timezone, rrule=rrule, alarms=alarms, span=span,
    ))


@app.command()
def delete(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    span: Annotated[str, typer.Option(help="this|future")] = "this",
) -> None:
    """Delete an event."""
    _output(delete_event(event_id, span=span))


def _validate_alarms(alarm: list[str] | None) -> list[str] | None:
    """Validate alarm list. Empty string must be sole value."""
    if alarm is None:
        return None
    if "" in alarm and len(alarm) > 1:
        msg = "Cannot combine --alarm '' (clear) with other alarm values"
        raise AlarmParseError(msg)
    return alarm


def run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except CalctlError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as e:  # noqa: BLE001
        logger.debug("Unexpected error", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(2) from None
```

Update `pyproject.toml` entry point to use `run`:
```toml
[project.scripts]
calctl = "calctl.cli:run"
```

- [ ] **Step 5: Run CLI tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All tests pass.

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 7: Run ruff and pyright**

Run:
```bash
uv run ruff check src/calctl/cli.py src/calctl/__init__.py tests/test_cli.py
uv run ruff format --check src/calctl/ tests/
uv run pyright src/calctl/cli.py
```
Expected: Clean.

- [ ] **Step 8: Commit**

```bash
git add src/calctl/cli.py src/calctl/__init__.py tests/test_cli.py pyproject.toml
git commit -m "feat: rewrite CLI with Typer — all subcommands, global options, error handling"
```

---

### Task 6: Full Validation Pass

Run all linters, type checkers, and tests. Fix any issues.

**Files:**
- May modify any source file to fix lint/type issues

- [ ] **Step 1: Run ruff check on everything**

Run: `uv run ruff check .`
Expected: No errors. Fix any that appear.

- [ ] **Step 2: Run ruff format on everything**

Run: `uv run ruff format --check .`
If failures: `uv run ruff format .` then verify.

- [ ] **Step 3: Run pyright on everything**

Run: `uv run pyright`
Expected: Zero errors. Warnings are OK for PyObjC types in `calendar.py`.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 5: Smoke test the CLI**

Run:
```bash
uv run calctl --help
uv run calctl calendars --format json
uv run calctl list --format text
uv run calctl list --format json --from 2026-03-19 --to 2026-03-26
```
Expected: Working output, no crashes.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve lint and type check issues"
```

---

### Task 7: README and Distribution Readiness

Write README, verify build works, ensure ready for PyPI.

**Files:**
- Rewrite: `README.md`

- [ ] **Step 1: Write README.md**

Write a complete README with:
- Title, one-line description
- Badges: (placeholders for PyPI version, Python version, License)
- **Features** section — bullet list of capabilities
- **Requirements** — macOS, Python ≥3.10
- **Installation** — `pipx install calctl` or `uv tool install calctl`
- **Permissions** — macOS calendar access note
- **Quick Start** — examples for each command (calendars, list, search, show, create, edit, delete)
- **CLI Reference** — all commands with all flags documented
- **Output Formats** — explain `--format json|text`, TTY auto-detection
- **License** — MIT

The README should be comprehensive enough to serve as the PyPI long description.

- [ ] **Step 2: Verify build**

Run:
```bash
uv build
ls dist/
```
Expected: `calctl-0.1.0.tar.gz` and `calctl-0.1.0-py3-none-any.whl` in `dist/`.

- [ ] **Step 3: Verify wheel contents**

Run:
```bash
unzip -l dist/calctl-0.1.0-py3-none-any.whl | grep calctl
```
Expected: All source files present including `py.typed`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README for PyPI/GitHub"
```

---

### Task 8: Final Integration Test

End-to-end verification that everything works together.

- [ ] **Step 1: Clean install test**

```bash
uv run --isolated calctl --help
```
Expected: Help text with all subcommands.

- [ ] **Step 2: Run all checks in sequence**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -v
```
Expected: All pass.

- [ ] **Step 3: Live smoke test (if calendar access available)**

```bash
uv run calctl calendars
uv run calctl list
uv run calctl list --format json
uv run calctl search "test"
```
Expected: Real calendar data or empty results (no crashes).

- [ ] **Step 4: Final commit and tag**

```bash
git add -A
git status
git commit -m "chore: final hardening cleanup" --allow-empty
git tag v0.1.0
git push origin main --tags
```
