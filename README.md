# calctl

**macOS Calendar CLI using EventKit**

[![PyPI version](https://img.shields.io/pypi/v/calctl.svg)](https://pypi.org/project/calctl/)
[![Python version](https://img.shields.io/pypi/pyversions/calctl.svg)](https://pypi.org/project/calctl/)
[![License](https://img.shields.io/pypi/l/calctl.svg)](https://github.com/ukaratay/calctl/blob/main/LICENSE)

`calctl` is a command-line interface for Apple Calendar on macOS. It uses the native EventKit framework via PyObjC — the same API the Calendar app uses — so it reads and writes all your calendars directly, with no sync or bridge required.

## Features

- **List calendars** — see all calendars with their source and type
- **List events** — browse events in any date range, filter by one or more calendars, exclude calendars
- **Search events** — full-text search across titles, notes, and locations
- **Create events** — all-day or timed events with full metadata
- **Edit events** — update any field; control whether edits apply to this occurrence or all future occurrences
- **Delete events** — single occurrence or this-and-future for recurring events
- **Recurring event safety** — auto-protects against accidentally wiping entire series when operating on the base event
- **Occurrence targeting** — `--date` flag to target a specific occurrence of a recurring event
- **Dry-run mode** — preview what `delete` and `edit` would do without making changes
- **Full EventKit support** — recurrence rules (RRULE), alarms, attendees, availability, geo coordinates, timezones
- **JSON and human-readable text output** — choose your format explicitly or let calctl detect it
- **Auto-detects output format** — JSON when piped, text when run in a terminal

## Requirements

- macOS (EventKit is macOS-only)
- Python ≥ 3.10

## Installation

```bash
# Using pipx (recommended for CLI tools)
pipx install calctl

# Using uv
uv tool install calctl
```

## Permissions

calctl needs access to your calendars. On first run, macOS will show a permission dialog. If you previously denied access, go to:

**System Settings → Privacy & Security → Calendars → calctl** → enable access

## Quick Start

```bash
# List all calendars
calctl calendars

# List events for the next 7 days
calctl list

# List events in a specific date range
calctl list --from 2026-03-19 --to 2026-03-26

# List events from a specific calendar
calctl list --calendar Work

# List events from multiple calendars
calctl list --calendar Work --calendar Family

# List events excluding certain calendars
calctl list --exclude-calendar Birthdays --exclude-calendar "US Holidays"

# Search events by keyword
calctl search "meeting"

# Search within a date range and calendar
calctl search "standup" --from 2026-03-01 --to 2026-03-31 --calendar Work

# Show full details for an event
calctl show EVENT_ID

# Show a specific occurrence of a recurring event
calctl show EVENT_ID --date 2026-03-25

# Create a timed event
calctl create --title "Team Standup" --start 2026-03-20T09:00:00 --end 2026-03-20T09:30:00 --calendar Work

# Create an all-day event
calctl create --title "Company Holiday" --start 2026-03-20 --all-day

# Create a recurring event with an alarm
calctl create \
  --title "Weekly Review" \
  --start 2026-03-20T14:00:00 \
  --rrule "FREQ=WEEKLY;BYDAY=FR" \
  --alarm -15m

# Create an event with location and geo coordinates
calctl create \
  --title "Lunch" \
  --start 2026-03-20T12:00:00 \
  --end 2026-03-20T13:00:00 \
  --location "Blue Bottle Coffee" \
  --geo "37.7749,-122.4194"

# Edit an event's title and location
calctl edit EVENT_ID --title "Updated Title" --location "Room 42"

# Edit a recurring event — this and all future occurrences
calctl edit EVENT_ID --title "Renamed Series" --span future

# Edit a specific occurrence by date
calctl edit EVENT_ID --date 2026-03-25 --title "Updated" --span this

# Preview what a delete would do
calctl delete EVENT_ID --dry-run

# Delete an event
calctl delete EVENT_ID

# Delete a specific occurrence of a recurring event
calctl delete EVENT_ID --date 2026-03-25 --span this

# Delete this and all future occurrences
calctl delete EVENT_ID --span future
```

## CLI Reference

### Global Options

These options apply to all commands and must come before the command name:

```
calctl [OPTIONS] COMMAND [ARGS]...
```

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--format` | `-f` | `json\|text` | auto | Output format. Defaults to `text` on TTY, `json` when piped. |
| `--verbose` | `-v` | flag | false | Enable debug logging to stderr. |
| `--help` | | flag | | Show help and exit. |

---

### `calctl calendars`

List all calendars.

```bash
calctl calendars
calctl calendars --format json
```

---

### `calctl list`

List events in a date range.

```bash
calctl list [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--from` | `YYYY-MM-DD` | today | Start date (inclusive). |
| `--to` | `YYYY-MM-DD` | today + 7 days | End date (inclusive). |
| `--calendar` | string | (all calendars) | Filter by calendar name. Repeatable for multiple calendars. |
| `--exclude-calendar` | string | (none) | Exclude calendar by name. Repeatable. |

**Examples:**

```bash
calctl list
calctl list --from 2026-03-01 --to 2026-03-31
calctl list --calendar Personal
calctl list --calendar Work --calendar Family
calctl list --exclude-calendar Birthdays --exclude-calendar "US Holidays"
```

---

### `calctl search`

Search events by keyword. Matches against title, notes, and location.

```bash
calctl search QUERY [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `QUERY` | string | required | Search keyword(s). |
| `--from` | `YYYY-MM-DD` | (no limit) | Restrict search start date. |
| `--to` | `YYYY-MM-DD` | (no limit) | Restrict search end date. |
| `--calendar` | string | (all calendars) | Filter by calendar name. Repeatable for multiple calendars. |
| `--exclude-calendar` | string | (none) | Exclude calendar by name. Repeatable. |

**Examples:**

```bash
calctl search "team meeting"
calctl search "invoice" --from 2026-01-01 --to 2026-03-31
calctl search "standup" --calendar Work
calctl search "meeting" --calendar Work --calendar Personal
```

---

### `calctl show`

Show full details for a single event, including recurrence, alarms, and attendees.

```bash
calctl show EVENT_ID [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `EVENT_ID` | string | **required** | Event identifier (from `list` or `search` output). |
| `--date` | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` | | Show the specific occurrence on this date instead of the base event. Use a datetime to disambiguate multiple same-day occurrences. |

**Examples:**

```bash
calctl show EVENT_ID
calctl show EVENT_ID --date 2026-03-25
```

---

### `calctl create`

Create a new event.

```bash
calctl create --title TITLE --start DATETIME [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--title` | string | **required** | Event title. |
| `--start` | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` | **required** | Start date or datetime. |
| `--end` | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` | start + 1h (or same day if `--all-day`) | End date or datetime. |
| `--calendar` | string | default calendar | Calendar to add the event to. |
| `--location` | string | | Location string. |
| `--geo` | `lat,lng` | | Geographic coordinates (e.g. `37.7749,-122.4194`). |
| `--notes` | string | | Event notes / description. |
| `--url` | string | | URL associated with the event. |
| `--all-day` / `--no-all-day` | flag | false | Create as an all-day event. |
| `--availability` | `busy\|free\|tentative\|unavailable` | | Availability status. |
| `--timezone` | string | | Timezone identifier (e.g. `America/New_York`). |
| `--rrule` | RRULE string | | Recurrence rule (e.g. `FREQ=WEEKLY;BYDAY=MO,WE,FR`). |
| `--alarm` | duration | | Alarm offset before event (e.g. `-15m`, `-1h`). Repeatable for multiple alarms. Use `--alarm ""` to explicitly clear alarms. |

**Examples:**

```bash
# Simple 30-minute event
calctl create --title "Coffee" --start 2026-03-20T10:00:00 --end 2026-03-20T10:30:00

# All-day event
calctl create --title "PTO" --start 2026-03-20 --all-day --calendar Personal

# Recurring weekly event with two alarms
calctl create \
  --title "Weekly Sync" \
  --start 2026-03-20T10:00:00 \
  --rrule "FREQ=WEEKLY;BYDAY=FR" \
  --alarm -10m \
  --alarm -1h

# Event with location details
calctl create \
  --title "Conference" \
  --start 2026-03-20T09:00:00 \
  --end 2026-03-20T17:00:00 \
  --location "Moscone Center, San Francisco" \
  --geo "37.7842,-122.4016" \
  --timezone "America/Los_Angeles"
```

---

### `calctl edit`

Edit an existing event. Only the fields you specify are changed.

```bash
calctl edit EVENT_ID [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `EVENT_ID` | string | **required** | Event to edit. |
| `--title` | string | | New title. |
| `--start` | datetime | | New start datetime. |
| `--end` | datetime | | New end datetime. |
| `--calendar` | string | | Move to this calendar. |
| `--location` | string | | New location string. |
| `--geo` | `lat,lng` | | New geo coordinates. |
| `--notes` | string | | New notes. |
| `--url` | string | | New URL. |
| `--all-day` / `--no-all-day` | flag | | Set or clear all-day flag. |
| `--availability` | `busy\|free\|tentative\|unavailable` | | New availability. |
| `--timezone` | string | | New timezone. |
| `--rrule` | RRULE string | | New recurrence rule. |
| `--alarm` | duration | | New alarm(s). Repeatable. Use `--alarm ""` to clear all alarms. |
| `--span` | `this\|future` | auto | For recurring events: edit only this occurrence (`this`) or this and all future occurrences (`future`). See [Recurring Events](#recurring-events). |
| `--date` | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` | | Target the occurrence on this date instead of the base event. Use a datetime to disambiguate multiple same-day occurrences. |
| `--dry-run` | flag | false | Show what would be changed without saving. |

**Examples:**

```bash
# Rename an event
calctl edit EVENT_ID --title "New Name"

# Reschedule
calctl edit EVENT_ID --start 2026-03-21T10:00:00 --end 2026-03-21T11:00:00

# Edit all future occurrences of a recurring event
calctl edit EVENT_ID --title "Renamed Series" --span future

# Edit a specific occurrence by date
calctl edit EVENT_ID --date 2026-03-25 --title "One-off change" --span this

# Move event to a different calendar
calctl edit EVENT_ID --calendar Personal

# Preview what would change
calctl edit EVENT_ID --title "New Name" --dry-run
```

---

### `calctl delete`

Delete an event.

```bash
calctl delete EVENT_ID [OPTIONS]
```

| Argument/Option | Type | Default | Description |
|-----------------|------|---------|-------------|
| `EVENT_ID` | string | **required** | Event to delete. |
| `--span` | `this\|future` | auto | For recurring events: delete only this occurrence (`this`) or this and all future occurrences (`future`). See [Recurring Events](#recurring-events). |
| `--date` | `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` | | Target the occurrence on this date instead of the base event. Use a datetime to disambiguate multiple same-day occurrences. |
| `--dry-run` | flag | false | Show what would be deleted without removing. |

**Examples:**

```bash
# Delete a single event
calctl delete EVENT_ID

# Delete this and all future occurrences
calctl delete EVENT_ID --span future

# Delete a specific occurrence by date
calctl delete EVENT_ID --date 2026-03-25 --span this

# Preview what would be deleted
calctl delete EVENT_ID --dry-run
```

---

## Recurring Events

calctl includes safety features to prevent accidentally modifying or deleting an entire recurring series.

### Span behavior

The `--span` flag on `edit` and `delete` controls whether the operation applies to a single occurrence or all future occurrences. When `--span` is **not** explicitly passed, calctl auto-detects:

- **Non-recurring event** → uses `this` (single event)
- **Base recurring event** (the series root, not a specific occurrence) → auto-escalates to `future` to preserve past occurrences, with a warning on stderr

If you explicitly pass `--span this` or `--span future`, your choice is always respected.

### Targeting a specific occurrence

`list` and `search` return the base event ID for recurring events. To target a specific occurrence, use `--date`:

```bash
# See the specific occurrence
calctl show EVENT_ID --date 2026-03-25

# Edit just that occurrence
calctl edit EVENT_ID --date 2026-03-25 --title "Rescheduled" --span this

# Delete just that occurrence
calctl delete EVENT_ID --date 2026-03-25 --span this
```

For events that recur multiple times in the same day, pass a full datetime to disambiguate:

```bash
calctl delete EVENT_ID --date 2026-03-25T14:00:00 --span this
```

### Identifying recurring events

Event output includes `is_recurring` and `occurrence_date` fields. In text format, recurring events show `Recurring: yes` with the recurrence rule. In list format, recurring events show a 🔁 icon with the RRULE.

---

## Output Formats

calctl supports two output formats, controlled by `--format` / `-f`:

| Format | Flag | Description |
|--------|------|-------------|
| `text` | `--format text` | Human-readable, table-style output for the terminal. |
| `json` | `--format json` | Machine-readable JSON. Arrays for list commands, objects for single-item commands. |

**Auto-detection:** When `--format` is not specified, calctl detects whether stdout is a terminal (TTY):
- **Terminal** → `text` format
- **Pipe or redirect** → `json` format

This means you can pipe calctl output to `jq` without specifying `--format json`:

```bash
# Pipe output — JSON is selected automatically
calctl list | jq '.[] | .title'
calctl search "meeting" | jq '.[0].id'

# Force text format in a script
calctl list --format text > events.txt
```

## License

MIT — see [LICENSE](LICENSE) for details.
