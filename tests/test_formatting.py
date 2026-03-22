"""Tests for calctl.formatting module."""

from __future__ import annotations

import datetime
import json

import pytest

from calctl.formatting import Format, format_output

# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

FULL_EVENT: dict = {
    "id": "abc-123",
    "title": "Team Standup",
    "start": "2026-03-19T09:00:00",
    "end": "2026-03-19T09:30:00",
    "all_day": False,
    "calendar": "Work",
    "location": "Conference Room A",
    "notes": "Daily sync",
    "url": "https://meet.example.com/standup",
    "availability": "busy",
    "status": "confirmed",
    "organizer": {"name": "Alice Smith", "email": "alice@example.com"},
    "attendees": [
        {"name": "Bob Jones", "status": "accepted"},
        {"name": "Carol White", "status": "tentative"},
    ],
    "alarms": ["-PT15M", "-PT5M"],
    "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
    "timezone": "America/New_York",
    "is_recurring": True,
    "is_detached": False,
    "occurrence_date": "2026-03-19T09:00:00",
    "geo": {"lat": 40.7128, "lng": -74.0060},
    "created": "2026-01-01T00:00:00",
    "modified": "2026-03-01T00:00:00",
}

MINIMAL_EVENT: dict = {
    "id": "min-1",
    "title": "Quick Meet",
    "start": "2026-03-20T14:00:00",
    "end": "2026-03-20T14:30:00",
    "all_day": False,
    "calendar": "Personal",
    "location": None,
    "notes": None,
    "url": None,
    "availability": None,
    "status": "none",
    "organizer": None,
    "attendees": None,
    "alarms": None,
    "rrule": None,
    "timezone": None,
    "is_recurring": False,
    "is_detached": False,
    "occurrence_date": None,
    "geo": None,
    "created": None,
    "modified": None,
}

ALL_DAY_EVENT: dict = {
    "id": "allday-1",
    "title": "Company Holiday",
    "start": "2026-07-04",
    "end": "2026-07-05",
    "all_day": True,
    "calendar": "Holidays",
    "location": None,
    "notes": None,
    "url": None,
    "availability": None,
    "status": "none",
    "organizer": None,
    "attendees": None,
    "alarms": None,
    "rrule": None,
    "timezone": None,
    "is_recurring": False,
    "is_detached": False,
    "occurrence_date": None,
    "geo": None,
    "created": None,
    "modified": None,
}

RECURRING_EVENT: dict = {
    "id": "rec-1",
    "title": "Weekly Review",
    "start": "2026-03-20T10:00:00",
    "end": "2026-03-20T11:00:00",
    "all_day": False,
    "calendar": "Work",
    "location": None,
    "notes": None,
    "url": None,
    "availability": None,
    "status": "none",
    "organizer": None,
    "attendees": None,
    "alarms": None,
    "rrule": "FREQ=WEEKLY;BYDAY=FR",
    "timezone": None,
    "is_recurring": True,
    "is_detached": False,
    "occurrence_date": "2026-03-20T10:00:00",
    "geo": None,
    "created": None,
    "modified": None,
}

CALENDAR_LIST: list[dict] = [
    {"name": "Work", "color": "#0000FF"},
    {"name": "Personal", "color": "#FF0000"},
    {"name": "Holidays", "color": "#00FF00"},
]


# ---------------------------------------------------------------------------
# JSON output tests
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_event_list_json(self) -> None:
        events = [MINIMAL_EVENT, ALL_DAY_EVENT]
        result = format_output(events, Format.json)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["title"] == "Quick Meet"
        assert parsed[1]["title"] == "Company Holiday"

    def test_calendar_list_json(self) -> None:
        result = format_output(CALENDAR_LIST, Format.json)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed[0]["name"] == "Work"

    def test_single_event_json(self) -> None:
        result = format_output(FULL_EVENT.copy(), Format.json)
        parsed = json.loads(result)
        assert parsed["title"] == "Team Standup"
        assert parsed["calendar"] == "Work"

    def test_empty_list_json(self) -> None:
        result = format_output([], Format.json)
        parsed = json.loads(result)
        assert parsed == []

    def test_action_key_stripped_in_json(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "created"}
        result = format_output(data, Format.json)
        parsed = json.loads(result)
        assert "_action" not in parsed
        assert parsed["title"] == "Quick Meet"

    def test_action_deleted_stripped_in_json(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "deleted"}
        result = format_output(data, Format.json)
        parsed = json.loads(result)
        assert "_action" not in parsed

    def test_json_indented(self) -> None:
        result = format_output({"key": "value"}, Format.json)
        assert "\n" in result  # indented

    def test_json_default_str_for_non_serializable(self) -> None:
        data = {"dt": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)}
        result = format_output(data, Format.json)
        parsed = json.loads(result)
        assert "2026" in parsed["dt"]


# ---------------------------------------------------------------------------
# Text output: event list
# ---------------------------------------------------------------------------


class TestTextEventList:
    def test_normal_event_list(self) -> None:
        events = [MINIMAL_EVENT]
        result = format_output(events, Format.text)
        assert "Quick Meet" in result
        assert "Personal" in result
        assert "14:00" in result
        assert "14:30" in result
        assert "2026-03-20" in result
        assert "\u2013" in result  # en-dash between times

    def test_all_day_event_in_list(self) -> None:
        result = format_output([ALL_DAY_EVENT], Format.text)
        assert "Company Holiday" in result
        assert "all day" in result
        assert "Holidays" in result

    def test_recurring_event_in_list(self) -> None:
        result = format_output([RECURRING_EVENT], Format.text)
        assert "Weekly Review" in result
        assert "\U0001f501" in result  # recurrence icon
        assert "FREQ=WEEKLY" in result

    def test_non_recurring_no_rrule_icon(self) -> None:
        result = format_output([MINIMAL_EVENT], Format.text)
        assert "\U0001f501" not in result

    def test_empty_event_list(self) -> None:
        result = format_output([], Format.text)
        assert result == "No events found."

    def test_multiple_events_one_per_line(self) -> None:
        events = [MINIMAL_EVENT, RECURRING_EVENT]
        result = format_output(events, Format.text)
        lines = result.strip().splitlines()
        assert len(lines) == 2

    def test_calendar_bracket_in_list(self) -> None:
        result = format_output([MINIMAL_EVENT], Format.text)
        assert "[Personal]" in result


# ---------------------------------------------------------------------------
# Text output: calendar list
# ---------------------------------------------------------------------------


class TestTextCalendarList:
    def test_calendar_list_format(self) -> None:
        result = format_output(CALENDAR_LIST, Format.text)
        assert "Work" in result
        assert "Personal" in result
        assert "Holidays" in result

    def test_calendar_list_indented(self) -> None:
        result = format_output(CALENDAR_LIST, Format.text)
        for line in result.splitlines():
            assert line.startswith("  ")

    def test_calendar_list_one_per_line(self) -> None:
        result = format_output(CALENDAR_LIST, Format.text)
        lines = result.strip().splitlines()
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# Text output: single event
# ---------------------------------------------------------------------------


class TestTextSingleEvent:
    def test_full_event_all_fields(self) -> None:
        result = format_output(FULL_EVENT.copy(), Format.text)
        assert "Team Standup" in result
        assert "Conference Room A" in result
        assert "https://meet.example.com/standup" in result
        assert "busy" in result
        assert "confirmed" in result
        assert "Alice Smith" in result
        assert "alice@example.com" in result
        assert "Bob Jones (accepted)" in result
        assert "Carol White (tentative)" in result
        assert "-PT15M" in result
        assert "-PT5M" in result
        assert "FREQ=WEEKLY" in result
        assert "America/New_York" in result
        assert "2026-01-01" in result
        assert "2026-03-01" in result
        assert "40.7128" in result
        assert "-74.006" in result

    def test_full_event_labels(self) -> None:
        result = format_output(FULL_EVENT.copy(), Format.text)
        assert "Title:" in result
        assert "Start:" in result
        assert "End:" in result
        assert "Calendar:" in result
        assert "Location:" in result
        assert "URL:" in result
        assert "Availability:" in result
        assert "Status:" in result
        assert "Organizer:" in result
        assert "Attendees:" in result
        assert "Alarms:" in result
        assert "Recurrence:" in result
        assert "Timezone:" in result
        assert "Created:" in result
        assert "Modified:" in result
        assert "Geo:" in result

    def test_all_day_event_shows_all_day_field(self) -> None:
        result = format_output(ALL_DAY_EVENT.copy(), Format.text)
        assert "All Day:" in result
        assert "yes" in result

    def test_minimal_event_omits_empty_fields(self) -> None:
        result = format_output(MINIMAL_EVENT.copy(), Format.text)
        assert "Location:" not in result
        assert "URL:" not in result
        assert "Availability:" not in result
        assert "Status:" not in result
        assert "Organizer:" not in result
        assert "Attendees:" not in result
        assert "Alarms:" not in result
        assert "Recurrence:" not in result
        assert "Timezone:" not in result
        assert "Created:" not in result
        assert "Modified:" not in result
        assert "Geo:" not in result
        assert "All Day:" not in result

    def test_minimal_event_has_required_fields(self) -> None:
        result = format_output(MINIMAL_EVENT.copy(), Format.text)
        assert "Quick Meet" in result
        assert "Personal" in result
        assert "Title:" in result
        assert "Start:" in result
        assert "End:" in result
        assert "Calendar:" in result

    def test_status_none_omitted(self) -> None:
        event = {**MINIMAL_EVENT.copy(), "status": "none"}
        result = format_output(event, Format.text)
        assert "Status:" not in result

    def test_availability_null_omitted(self) -> None:
        event = {**MINIMAL_EVENT.copy(), "availability": None}
        result = format_output(event, Format.text)
        assert "Availability:" not in result

    def test_organizer_without_email(self) -> None:
        event = {**FULL_EVENT.copy(), "organizer": {"name": "Bob", "email": None}}
        result = format_output(event, Format.text)
        assert "Bob" in result
        assert "<" not in result or "alice@example.com" not in result

    def test_geo_field_formatted(self) -> None:
        result = format_output(FULL_EVENT.copy(), Format.text)
        geo_line = next(line for line in result.splitlines() if "Geo:" in line)
        assert "40.7128" in geo_line
        assert "-74.006" in geo_line


# ---------------------------------------------------------------------------
# Text output: action messages
# ---------------------------------------------------------------------------


class TestTextActionMessages:
    def test_created_action_has_prefix(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "created"}
        result = format_output(data, Format.text)
        assert result.startswith("\u2713 Created:")
        assert "Quick Meet" in result

    def test_created_action_includes_event_details(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "created"}
        result = format_output(data, Format.text)
        assert "Title:" in result
        assert "Start:" in result
        assert "Calendar:" in result

    def test_updated_action_has_prefix(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "updated"}
        result = format_output(data, Format.text)
        assert result.startswith("\u2713 Updated:")
        assert "Quick Meet" in result

    def test_updated_action_includes_event_details(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "updated"}
        result = format_output(data, Format.text)
        assert "Title:" in result
        assert "Calendar:" in result

    def test_deleted_action_one_line(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "deleted"}
        result = format_output(data, Format.text)
        assert result.startswith("\u2713 Event deleted:")
        assert "Quick Meet" in result
        # deleted is a single line (no multi-line key-value block)
        lines = result.strip().splitlines()
        assert len(lines) == 1

    def test_deleted_includes_date(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "deleted"}
        result = format_output(data, Format.text)
        assert "2026-03-20" in result

    def test_unknown_action_uses_generic_prefix(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "archived"}
        result = format_output(data, Format.text)
        assert "\u2713 archived:" in result

    def test_created_full_event(self) -> None:
        data = {**FULL_EVENT.copy(), "_action": "created"}
        result = format_output(data, Format.text)
        assert "\u2713 Created:" in result
        assert "Team Standup" in result
        assert "Alice Smith" in result

    def test_dry_run_action_no_checkmark(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "dry_run", "span": "future"}
        result = format_output(data, Format.text)
        assert "[DRY RUN]" in result
        assert "span=future" in result
        assert "\u2713" not in result

    def test_dry_run_includes_event_details(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "dry_run", "span": "this"}
        result = format_output(data, Format.text)
        assert "Quick Meet" in result

    def test_action_does_not_mutate_input(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "created"}
        format_output(data, Format.text)
        assert "_action" in data

    def test_json_strips_all_underscore_keys(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "dry_run", "_internal": "x"}
        result = format_output(data, Format.json)
        parsed = json.loads(result)
        assert "_action" not in parsed
        assert "_internal" not in parsed

    def test_json_keeps_span_field(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "dry_run", "span": "future"}
        result = format_output(data, Format.json)
        parsed = json.loads(result)
        assert parsed["span"] == "future"


# ---------------------------------------------------------------------------
# Format enum tests
# ---------------------------------------------------------------------------


class TestFormatEnum:
    def test_json_value(self) -> None:
        assert Format.json == "json"
        assert Format.json.value == "json"

    def test_text_value(self) -> None:
        assert Format.text == "text"
        assert Format.text.value == "text"

    def test_format_is_str(self) -> None:
        assert isinstance(Format.json, str)
        assert isinstance(Format.text, str)

    def test_format_from_string(self) -> None:
        assert Format("json") is Format.json
        assert Format("text") is Format.text

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="'xml' is not a valid Format"):
            Format("xml")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_non_dict_non_list_falls_through(self) -> None:
        result = format_output("hello", Format.text)
        assert result == "hello"

    def test_integer_falls_through(self) -> None:
        result = format_output(42, Format.text)
        assert result == "42"

    def test_action_key_not_in_output_text(self) -> None:
        data = {**MINIMAL_EVENT.copy(), "_action": "created"}
        result = format_output(data, Format.text)
        assert "_action" not in result

    def test_event_list_with_all_day_and_normal(self) -> None:
        events = [ALL_DAY_EVENT, MINIMAL_EVENT]
        result = format_output(events, Format.text)
        lines = result.strip().splitlines()
        assert len(lines) == 2
        assert "all day" in lines[0]
        assert "\u2013" in lines[1]
