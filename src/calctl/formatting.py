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
    # Dict with _action key -> action message
    if isinstance(data, dict) and "_action" in data:
        return _format_action(data)

    # Dict with id + title -> single event
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
            line += f"  \U0001f501 {e['rrule']}"

        lines.append(line)
    return "\n".join(lines)


def _format_calendar_list(calendars: list[dict[str, Any]]) -> str:
    """Format a list of calendars."""
    if not calendars:
        return "No calendars found."
    return "\n".join(f"  {c['name']}" for c in calendars)


def _format_single_event(event: dict[str, Any], prefix: str = "") -> str:  # noqa: C901, PLR0912
    """Format a single event as key-value pairs."""
    lines: list[str] = []
    if prefix:
        lines.append(prefix)

    lines.append(f"{'Title:':<14}{event['title']}")
    lines.append(f"{'Start:':<14}{event['start']}")
    lines.append(f"{'End:':<14}{event['end']}")

    if event.get("all_day"):
        lines.append(f"{'All Day:':<14}yes")

    lines.append(f"{'Calendar:':<14}{event['calendar']}")

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
        return f"\u2713 Event deleted: {data['title']} ({start_date})"

    prefix_map = {"created": "\u2713 Created:", "updated": "\u2713 Updated:"}
    prefix = prefix_map.get(action, f"\u2713 {action}:")
    return _format_single_event(data, prefix=prefix)
