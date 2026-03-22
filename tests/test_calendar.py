"""Tests for calctl.calendar module."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from calctl.errors import (
    AlarmParseError,
    CalctlError,
    CalendarNotFoundError,
    DateParseError,
    EventNotFoundError,
    EventSaveError,
    RRuleParseError,
)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

# ---------------------------------------------------------------------------
# Helpers (import after skipif so non-darwin won't choke on missing modules)
# ---------------------------------------------------------------------------


def _get_cal(patched_calendar: Any) -> Any:
    return patched_calendar


# ---------------------------------------------------------------------------
# _ns_date / date parsing
# ---------------------------------------------------------------------------


class TestNsDate:
    def test_valid_datetime(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        result = cal._ns_date("2026-03-19T10:00:00")
        assert result is not None

    def test_valid_date_only(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        result = cal._ns_date("2026-03-19")
        assert result is not None

    def test_invalid_date_raises(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        # The mock formatter returns a mock for any string.
        # We test the real logic by patching formatter to return None.
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_foundation") as mock_fd_factory:
            fd = MagicMock()
            formatter_inst = MagicMock()
            formatter_inst.dateFromString_.return_value = None
            fd.NSDateFormatter.alloc.return_value.init.return_value = formatter_inst
            fd.NSTimeZone.localTimeZone.return_value = MagicMock()
            mock_fd_factory.return_value = fd
            with pytest.raises(DateParseError, match="Cannot parse date"):
                real_cal._ns_date("not-a-date")


# ---------------------------------------------------------------------------
# _format_alarm
# ---------------------------------------------------------------------------


class TestFormatAlarm:
    def test_relative_minutes(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_alarm

        alarm = _make_mock_alarm(relative_offset=-900)
        assert cal._format_alarm(alarm) == "-15m"

    def test_relative_hours(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_alarm

        alarm = _make_mock_alarm(relative_offset=-3600)
        assert cal._format_alarm(alarm) == "-1h"

    def test_relative_days(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_alarm

        alarm = _make_mock_alarm(relative_offset=-172800)
        assert cal._format_alarm(alarm) == "-2d"

    def test_absolute_alarm(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_alarm

        alarm = _make_mock_alarm(absolute_iso="2026-03-20T09:00:00")
        result = cal._format_alarm(alarm)
        assert "2026-03-20" in result


# ---------------------------------------------------------------------------
# _parse_alarm
# ---------------------------------------------------------------------------


class TestParseAlarm:
    def test_relative_minutes(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        alarm = cal._parse_alarm("-15m")
        assert alarm is not None

    def test_relative_hours(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        alarm = cal._parse_alarm("-1h")
        assert alarm is not None

    def test_relative_days(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        alarm = cal._parse_alarm("-2d")
        assert alarm is not None

    def test_absolute_alarm(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        alarm = cal._parse_alarm("2026-03-20T09:00:00")
        assert alarm is not None

    def test_invalid_raises(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_foundation") as mock_fd_factory:
            fd = MagicMock()
            formatter_inst = MagicMock()
            formatter_inst.dateFromString_.return_value = None
            fd.NSDateFormatter.alloc.return_value.init.return_value = formatter_inst
            fd.NSTimeZone.localTimeZone.return_value = MagicMock()
            mock_fd_factory.return_value = fd
            # also patch _import_eventkit to stop early alarm parsing
            with pytest.raises(AlarmParseError, match="Cannot parse alarm"):
                real_cal._parse_alarm("not-an-alarm")


# ---------------------------------------------------------------------------
# _parse_geo
# ---------------------------------------------------------------------------


class TestParseGeo:
    def test_valid_geo(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        lat, lng = cal._parse_geo("37.7749,-122.4194")
        assert abs(lat - 37.7749) < 1e-4
        assert abs(lng - (-122.4194)) < 1e-4

    def test_invalid_format_no_comma(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        with pytest.raises(CalctlError, match="Invalid geo format"):
            cal._parse_geo("37.7749")

    def test_invalid_format_non_numeric(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        with pytest.raises(CalctlError, match="Invalid geo format"):
            cal._parse_geo("abc,def")

    def test_too_many_parts(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        with pytest.raises(CalctlError, match="Invalid geo format"):
            cal._parse_geo("37.7749,-122.4194,100")


# ---------------------------------------------------------------------------
# _event_to_dict — full field coverage
# ---------------------------------------------------------------------------


class TestEventToDict:
    def test_basic_fields(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event()
        result = cal._event_to_dict(event)

        assert result["id"] == "evt-001"
        assert result["title"] == "Test Meeting"
        assert "2026-03-19" in result["start"]
        assert "2026-03-19" in result["end"]
        assert result["all_day"] is False
        assert result["calendar"] == "Work"
        assert result["is_detached"] is False

    def test_availability_busy(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(availability=0)
        result = cal._event_to_dict(event)
        assert result["availability"] == "busy"

    def test_availability_free(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(availability=1)
        result = cal._event_to_dict(event)
        assert result["availability"] == "free"

    def test_availability_not_supported(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(availability=-1)
        result = cal._event_to_dict(event)
        assert result["availability"] is None

    def test_status_confirmed(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(status=1)
        result = cal._event_to_dict(event)
        assert result["status"] == "confirmed"

    def test_organizer(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_participant

        org = _make_mock_participant("Jane", "jane@example.com")
        event = _make_mock_event(organizer=org)
        result = cal._event_to_dict(event)
        assert result["organizer"] is not None
        assert result["organizer"]["name"] == "Jane"
        assert result["organizer"]["email"] == "jane@example.com"

    def test_attendees(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_participant

        attendees = [
            _make_mock_participant("Bob", "bob@example.com", status=2, role=1),
            _make_mock_participant("Alice", "alice@example.com", status=4, role=2),
        ]
        event = _make_mock_event(attendees=attendees)
        result = cal._event_to_dict(event)
        assert len(result["attendees"]) == 2
        assert result["attendees"][0]["name"] == "Bob"
        assert result["attendees"][0]["status"] == "accepted"
        assert result["attendees"][1]["status"] == "tentative"
        assert result["attendees"][1]["role"] == "optional"

    def test_alarms_relative(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_alarm

        alarms = [
            _make_mock_alarm(relative_offset=-900),
            _make_mock_alarm(relative_offset=-3600),
        ]
        event = _make_mock_event(alarms=alarms)
        result = cal._event_to_dict(event)
        assert "-15m" in result["alarms"]
        assert "-1h" in result["alarms"]

    def test_geo_from_struct_location(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        struct_loc = MagicMock()
        geo_loc = MagicMock()
        coord = MagicMock()
        coord.latitude = 37.7749
        coord.longitude = -122.4194
        geo_loc.coordinate.return_value = coord
        struct_loc.geoLocation.return_value = geo_loc
        event = _make_mock_event(struct_location=struct_loc)
        result = cal._event_to_dict(event)
        assert result["geo"] is not None
        assert abs(result["geo"]["lat"] - 37.7749) < 1e-4
        assert abs(result["geo"]["lng"] - (-122.4194)) < 1e-4

    def test_no_geo(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(struct_location=None)
        result = cal._event_to_dict(event)
        assert result["geo"] is None

    def test_url(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(url_str="https://meet.example.com/123")
        result = cal._event_to_dict(event)
        assert result["url"] == "https://meet.example.com/123"

    def test_timezone(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(timezone_name="America/New_York")
        result = cal._event_to_dict(event)
        assert result["timezone"] == "America/New_York"

    def test_created_modified(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(
            created_iso="2026-03-18T09:00:00",
            modified_iso="2026-03-18T15:00:00",
        )
        result = cal._event_to_dict(event)
        assert result["created"] is not None
        assert result["modified"] is not None

    def test_rrule_from_recurrence_rule(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        # weekly rule with MO, WE, FR
        days = []
        for day_int in [2, 4, 6]:  # MO=1, WE=3, FR=5 in EK indexing (SU=0)
            d = MagicMock()
            d.dayOfTheWeek.return_value = day_int
            d.weekNumber.return_value = 0
            days.append(d)
        rule = _make_mock_recurrence_rule(freq=1, days_of_week=days)
        rule.recurrenceEnd.return_value = None
        event = _make_mock_event(recurrence_rules=[rule])
        result = cal._event_to_dict(event)
        assert result["rrule"] is not None
        assert "FREQ=WEEKLY" in result["rrule"]

    def test_all_fields_present(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event()
        result = cal._event_to_dict(event)
        expected_keys = {
            "id",
            "title",
            "start",
            "end",
            "all_day",
            "location",
            "geo",
            "notes",
            "calendar",
            "url",
            "availability",
            "status",
            "organizer",
            "attendees",
            "alarms",
            "rrule",
            "timezone",
            "is_detached",
            "created",
            "modified",
        }
        assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# list_calendars
# ---------------------------------------------------------------------------


class TestListCalendars:
    def test_returns_list(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_calendar

        mock_store.calendarsForEntityType_.return_value = [
            _make_mock_calendar("Work", "cal-1"),
            _make_mock_calendar("Personal", "cal-2"),
        ]
        result = cal.list_calendars()
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "Work" in names
        assert "Personal" in names

    def test_returns_ids(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_calendar

        mock_store.calendarsForEntityType_.return_value = [
            _make_mock_calendar("Work", "cal-abc"),
        ]
        result = cal.list_calendars()
        assert result[0]["id"] == "cal-abc"


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_returns_events(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        events = [
            _make_mock_event("e1", "Meeting 1"),
            _make_mock_event("e2", "Meeting 2"),
        ]
        mock_store.eventsMatchingPredicate_.return_value = events
        result = cal.list_events("2026-03-01", "2026-03-31")
        assert len(result) == 2

    def test_unknown_calendar_returns_empty(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_calendar

        mock_store.calendarsForEntityType_.return_value = [_make_mock_calendar("Work")]
        result = cal.list_events("2026-03-01", "2026-03-31", calendar="NonExistent")
        assert result == []

    def test_date_range_validation(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        # from > to should raise DateParseError
        import calctl.calendar as real_cal

        # We need to test the actual date comparison logic.
        # Patch _ns_date to return objects with predictable compare_ results.
        from tests.conftest import _make_ns_date_mock

        early = _make_ns_date_mock("2026-03-01T00:00:00")
        late = _make_ns_date_mock("2026-03-31T00:00:00")

        with patch.object(real_cal, "_ns_date") as mock_ns_date:
            mock_ns_date.side_effect = [late, early]  # from > to
            with pytest.raises(
                DateParseError, match="Start date must be before end date"
            ):
                real_cal.list_events("2026-03-31", "2026-03-01")

    def test_filtered_by_calendar(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_calendar

        events = [_make_mock_event("e1", "Work Meeting")]
        mock_store.eventsMatchingPredicate_.return_value = events
        work_cal = _make_mock_calendar("Work")
        mock_store.calendarsForEntityType_.return_value = [work_cal]
        result = cal.list_events("2026-03-01", "2026-03-31", calendar="Work")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# search_events
# ---------------------------------------------------------------------------


class TestSearchEvents:
    def test_search_by_title(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        events = [
            _make_mock_event("e1", "Team Standup"),
            _make_mock_event("e2", "Dentist Appointment"),
        ]
        mock_store.eventsMatchingPredicate_.return_value = events
        result = cal.search_events("standup")
        assert len(result) == 1
        assert result[0]["title"] == "Team Standup"

    def test_search_by_notes(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        events = [
            _make_mock_event("e1", "Meeting", notes="quarterly review"),
        ]
        mock_store.eventsMatchingPredicate_.return_value = events
        result = cal.search_events("quarterly")
        assert len(result) == 1

    def test_search_no_results(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        events = [_make_mock_event("e1", "Team Standup")]
        mock_store.eventsMatchingPredicate_.return_value = events
        result = cal.search_events("xyznotfound")
        assert result == []

    def test_search_with_calendar_filter(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_calendar

        mock_store.calendarsForEntityType_.return_value = [_make_mock_calendar("Work")]
        mock_store.eventsMatchingPredicate_.return_value = []
        result = cal.search_events("meeting", calendar="Work")
        assert result == []

    def test_search_unknown_calendar_returns_empty(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_calendar

        mock_store.calendarsForEntityType_.return_value = [_make_mock_calendar("Work")]
        result = cal.search_events("meeting", calendar="NonExistent")
        assert result == []


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_returns_event(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("evt-abc", "Test Event")
        mock_store.eventWithIdentifier_.return_value = event
        result = cal.get_event("evt-abc")
        assert result["id"] == "evt-abc"
        assert result["title"] == "Test Event"

    def test_raises_event_not_found(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        mock_store.eventWithIdentifier_.return_value = None
        with pytest.raises(EventNotFoundError, match="Event not found"):
            cal.get_event("nonexistent-id")


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


class TestCreateEvent:
    def test_creates_event_basic(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_calendar

        new_event = _make_mock_event("new-evt", "New Meeting")
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        mock_store.saveEvent_span_error_.return_value = (True, None)
        mock_store.calendarsForEntityType_.return_value = [_make_mock_calendar("Work")]
        mock_store.defaultCalendarForNewEvents.return_value = _make_mock_calendar()

        result = cal.create_event("New Meeting", "2026-03-20T10:00:00")
        assert result["title"] == "New Meeting"
        assert result["_action"] == "created"

    def test_raises_calendar_not_found(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_calendar

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        mock_store.calendarsForEntityType_.return_value = [
            _make_mock_calendar("Personal")
        ]

        with pytest.raises(CalendarNotFoundError, match="Calendar not found"):
            cal.create_event("Meeting", "2026-03-20T10:00:00", calendar="NonExistent")

    def test_raises_event_save_error(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        err = MagicMock()
        err.localizedDescription.return_value = "Permission error"
        mock_store.saveEvent_span_error_.return_value = (False, err)

        with pytest.raises(EventSaveError, match="Failed to save event"):
            cal.create_event("Meeting", "2026-03-20T10:00:00")

    def test_end_before_start_raises(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event
        import calctl.calendar as real_cal

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event

        from tests.conftest import _make_ns_date_mock

        start_ns = _make_ns_date_mock("2026-03-20T11:00:00")
        end_ns = _make_ns_date_mock("2026-03-20T09:00:00")

        with patch.object(real_cal, "_ns_date") as mock_ns_date:
            mock_ns_date.side_effect = [start_ns, end_ns]
            with pytest.raises(
                DateParseError, match="End time must be after start time"
            ):
                real_cal.create_event(
                    "Meeting", "2026-03-20T11:00:00", end="2026-03-20T09:00:00"
                )

    def test_creates_with_alarms(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        result = cal.create_event(
            "Meeting", "2026-03-20T10:00:00", alarms=["-15m", "-1h"]
        )
        assert result["_action"] == "created"
        new_event.setAlarms_.assert_called()

    def test_creates_with_geo(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        result = cal.create_event(
            "Meeting", "2026-03-20T10:00:00", location="HQ", geo="37.7749,-122.4194"
        )
        assert result["_action"] == "created"
        new_event.setStructuredLocation_.assert_called()

    def test_invalid_availability_raises(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        mock_eventkit.EKEvent.eventWithEventStore_.return_value = _make_mock_event()

        with pytest.raises(CalctlError, match="Invalid availability"):
            cal.create_event("Meeting", "2026-03-20T10:00:00", availability="invalid")

    def test_default_end_one_hour_after(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        new_event = _make_mock_event()
        mock_eventkit.EKEvent.eventWithEventStore_.return_value = new_event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.create_event("Meeting", "2026-03-20T10:00:00")
        new_event.setEndDate_.assert_called()


# ---------------------------------------------------------------------------
# edit_event
# ---------------------------------------------------------------------------


class TestEditEvent:
    def test_edits_title(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", "Old Title")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        result = cal.edit_event("e1", title="New Title")
        assert result["_action"] == "updated"
        event.setTitle_.assert_called_with("New Title")

    def test_raises_event_not_found(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        mock_store.eventWithIdentifier_.return_value = None
        with pytest.raises(EventNotFoundError):
            cal.edit_event("nonexistent", title="New")

    def test_raises_save_error(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        err = MagicMock()
        err.localizedDescription.return_value = "Disk full"
        mock_store.saveEvent_span_error_.return_value = (False, err)

        with pytest.raises(EventSaveError, match="Failed to edit event"):
            cal.edit_event("e1", title="New Title")

    def test_calendar_move(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_calendar

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)
        personal_cal = _make_mock_calendar("Personal", "cal-2")
        mock_store.calendarsForEntityType_.return_value = [
            _make_mock_calendar("Work", "cal-1"),
            personal_cal,
        ]

        result = cal.edit_event("e1", calendar="Personal")
        assert result["_action"] == "updated"
        event.setCalendar_.assert_called_with(personal_cal)

    def test_calendar_move_not_found_raises(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_calendar

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.calendarsForEntityType_.return_value = [_make_mock_calendar("Work")]

        with pytest.raises(CalendarNotFoundError):
            cal.edit_event("e1", calendar="NonExistent")

    def test_span_future(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", title="Updated", span="future")
        mock_store.saveEvent_span_error_.assert_called_with(
            event, mock_eventkit.EKSpanFutureEvents, None
        )

    def test_clear_notes(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", notes="old notes")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", notes="")
        event.setNotes_.assert_called_with(None)

    def test_clear_rrule(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule()
        event = _make_mock_event("e1", recurrence_rules=[rule])
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", rrule="")
        event.removeRecurrenceRule_.assert_called()

    def test_clear_alarms(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_alarm

        alarms = [_make_mock_alarm(relative_offset=-900)]
        event = _make_mock_event("e1", alarms=alarms)
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", alarms=[""])
        event.setAlarms_.assert_called_with(None)

    def test_clear_url(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", url_str="https://old.example.com")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", url="")
        event.setURL_.assert_called_with(None)

    def test_clear_timezone(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", timezone_name="America/New_York")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", timezone="")
        event.setTimeZone_.assert_called_with(None)

    def test_clear_geo(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        cal.edit_event("e1", geo="")
        event.setStructuredLocation_.assert_called_with(None)

    def test_end_before_start_raises(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        import calctl.calendar as real_cal
        from tests.conftest import _make_mock_event, _make_ns_date_mock

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event

        late = _make_ns_date_mock("2026-03-20T11:00:00")
        early = _make_ns_date_mock("2026-03-20T09:00:00")
        # current start is "late"; end we're setting is "early"
        event.startDate.return_value = late

        with patch.object(real_cal, "_ns_date", return_value=early):
            with pytest.raises(
                DateParseError, match="End time must be after start time"
            ):
                real_cal.edit_event("e1", end="2026-03-20T09:00:00")


# ---------------------------------------------------------------------------
# delete_event
# ---------------------------------------------------------------------------


class TestDeleteEvent:
    def test_deletes_event(self, patched_calendar: Any, mock_store: MagicMock) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", "Meeting")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.removeEvent_span_error_.return_value = (True, None)

        result = cal.delete_event("e1")
        assert result["_action"] == "deleted"
        assert result["id"] == "e1"

    def test_raises_event_not_found(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        mock_store.eventWithIdentifier_.return_value = None
        with pytest.raises(EventNotFoundError):
            cal.delete_event("nonexistent")

    def test_raises_save_error_on_delete_failure(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        err = MagicMock()
        err.localizedDescription.return_value = "Access denied"
        mock_store.removeEvent_span_error_.return_value = (False, err)

        with pytest.raises(EventSaveError, match="Failed to delete event"):
            cal.delete_event("e1")

    def test_span_future(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.removeEvent_span_error_.return_value = (True, None)

        cal.delete_event("e1", span="future")
        mock_store.removeEvent_span_error_.assert_called_with(
            event, mock_eventkit.EKSpanFutureEvents, None
        )

    def test_span_this_default(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1")
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.removeEvent_span_error_.return_value = (True, None)

        cal.delete_event("e1")
        mock_store.removeEvent_span_error_.assert_called_with(
            event, mock_eventkit.EKSpanThisEvent, None
        )


# ---------------------------------------------------------------------------
# RRULE round-trip tests
# ---------------------------------------------------------------------------


class TestRrule:
    def test_ek_to_rrule_weekly(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1, interval=1)
        rule.recurrenceEnd.return_value = None
        result = cal._ek_to_rrule(rule)
        assert "RRULE:FREQ=WEEKLY" in result

    def test_ek_to_rrule_daily_with_count(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        end = MagicMock()
        end.occurrenceCount.return_value = 10
        end.endDate.return_value = None
        rule = _make_mock_recurrence_rule(freq=0, interval=1)
        rule.recurrenceEnd.return_value = end
        result = cal._ek_to_rrule(rule)
        assert "FREQ=DAILY" in result
        assert "COUNT=10" in result

    def test_ek_to_rrule_with_byday(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        days = []
        for day_int in [1, 3, 5]:  # MO, WE, FR
            d = MagicMock()
            d.dayOfTheWeek.return_value = day_int
            d.weekNumber.return_value = 0
            days.append(d)
        rule = _make_mock_recurrence_rule(freq=1, days_of_week=days)
        rule.recurrenceEnd.return_value = None
        result = cal._ek_to_rrule(rule)
        assert "BYDAY=" in result

    def test_ek_to_rrule_monthly(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=2, interval=1, days_of_month=[15])
        rule.recurrenceEnd.return_value = None
        result = cal._ek_to_rrule(rule)
        assert "FREQ=MONTHLY" in result
        assert "BYMONTHDAY=15" in result

    def test_ek_to_rrule_yearly(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=3, interval=1, months_of_year=[3])
        rule.recurrenceEnd.return_value = None
        result = cal._ek_to_rrule(rule)
        assert "FREQ=YEARLY" in result
        assert "BYMONTH=3" in result

    def test_ek_to_rrule_with_interval(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1, interval=2)
        rule.recurrenceEnd.return_value = None
        result = cal._ek_to_rrule(rule)
        assert "INTERVAL=2" in result

    def test_rrule_to_ek_weekly_byday(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_eventkit", return_value=mock_eventkit):
            result = real_cal._rrule_to_ek("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR")
            assert result is not None

    def test_rrule_to_ek_daily_count(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_eventkit", return_value=mock_eventkit):
            result = real_cal._rrule_to_ek("RRULE:FREQ=DAILY;COUNT=5")
            assert result is not None

    def test_rrule_to_ek_invalid_raises(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_eventkit", return_value=mock_eventkit):
            with pytest.raises(RRuleParseError, match="Invalid RRULE"):
                real_cal._rrule_to_ek("RRULE:FREQ=INVALID_FREQ_XYZ")

    def test_rrule_to_ek_monthly_bymonthday(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_eventkit", return_value=mock_eventkit):
            result = real_cal._rrule_to_ek("RRULE:FREQ=MONTHLY;BYMONTHDAY=15")
            assert result is not None

    def test_rrule_to_ek_yearly(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        import calctl.calendar as real_cal

        with patch.object(real_cal, "_import_eventkit", return_value=mock_eventkit):
            result = real_cal._rrule_to_ek("RRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=15")
            assert result is not None


# ---------------------------------------------------------------------------
# _span_constant validation
# ---------------------------------------------------------------------------


class TestSpanConstant:
    def test_this_returns_ek_span(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        result = cal._span_constant("this")
        assert result == mock_eventkit.EKSpanThisEvent

    def test_future_returns_ek_span(
        self, patched_calendar: Any, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        result = cal._span_constant("future")
        assert result == mock_eventkit.EKSpanFutureEvents

    def test_invalid_span_raises(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        with pytest.raises(CalctlError, match="Invalid span"):
            cal._span_constant("all")

    def test_typo_span_raises(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        with pytest.raises(CalctlError, match="Invalid span"):
            cal._span_constant("futur")


# ---------------------------------------------------------------------------
# _is_base_recurring_event
# ---------------------------------------------------------------------------


class TestIsBaseRecurringEvent:
    def test_non_recurring_event(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(recurrence_rules=[])
        assert cal._is_base_recurring_event(event) is False

    def test_base_recurring_event(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event(recurrence_rules=[rule], is_detached=False)
        assert cal._is_base_recurring_event(event) is True

    def test_detached_occurrence(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event(recurrence_rules=[rule], is_detached=True)
        assert cal._is_base_recurring_event(event) is False


# ---------------------------------------------------------------------------
# _resolve_span — auto-escalation for base recurring events
# ---------------------------------------------------------------------------


class TestResolveSpan:
    def test_non_recurring_stays_this(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event(recurrence_rules=[])
        assert cal._resolve_span(event, "this") == "this"

    def test_base_recurring_escalates_to_future(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event(recurrence_rules=[rule], is_detached=False)
        assert cal._resolve_span(event, "this") == "future"

    def test_explicit_future_unchanged(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event(recurrence_rules=[rule], is_detached=False)
        assert cal._resolve_span(event, "future") == "future"

    def test_detached_occurrence_stays_this(self, patched_calendar: Any) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event(recurrence_rules=[rule], is_detached=True)
        assert cal._resolve_span(event, "this") == "this"


# ---------------------------------------------------------------------------
# delete_event — dry_run and span escalation
# ---------------------------------------------------------------------------


class TestDeleteEventDryRun:
    def test_dry_run_returns_without_deleting(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", "Meeting")
        mock_store.eventWithIdentifier_.return_value = event

        result = cal.delete_event("e1", dry_run=True)
        assert result["_action"] == "dry_run"
        assert result["_span"] == "this"
        mock_store.removeEvent_span_error_.assert_not_called()

    def test_dry_run_escalates_base_recurring(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event("e1", "Weekly Sync", recurrence_rules=[rule])
        mock_store.eventWithIdentifier_.return_value = event

        result = cal.delete_event("e1", dry_run=True)
        assert result["_action"] == "dry_run"
        assert result["_span"] == "future"
        mock_store.removeEvent_span_error_.assert_not_called()

    def test_delete_base_recurring_auto_escalates(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event("e1", "Weekly Sync", recurrence_rules=[rule])
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.removeEvent_span_error_.return_value = (True, None)

        result = cal.delete_event("e1")
        assert result["_action"] == "deleted"
        assert result["_span"] == "future"
        mock_store.removeEvent_span_error_.assert_called_with(
            event, mock_eventkit.EKSpanFutureEvents, None
        )


# ---------------------------------------------------------------------------
# edit_event — dry_run and span escalation
# ---------------------------------------------------------------------------


class TestEditEventDryRun:
    def test_dry_run_returns_without_saving(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event

        event = _make_mock_event("e1", "Meeting")
        mock_store.eventWithIdentifier_.return_value = event

        result = cal.edit_event("e1", title="New Title", dry_run=True)
        assert result["_action"] == "dry_run"
        assert result["_span"] == "this"
        event.setTitle_.assert_not_called()
        mock_store.saveEvent_span_error_.assert_not_called()

    def test_dry_run_escalates_base_recurring(
        self, patched_calendar: Any, mock_store: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event("e1", "Weekly Sync", recurrence_rules=[rule])
        mock_store.eventWithIdentifier_.return_value = event

        result = cal.edit_event("e1", title="X", dry_run=True)
        assert result["_action"] == "dry_run"
        assert result["_span"] == "future"
        mock_store.saveEvent_span_error_.assert_not_called()

    def test_edit_base_recurring_auto_escalates(
        self, patched_calendar: Any, mock_store: MagicMock, mock_eventkit: MagicMock
    ) -> None:
        cal = _get_cal(patched_calendar)
        from tests.conftest import _make_mock_event, _make_mock_recurrence_rule

        rule = _make_mock_recurrence_rule(freq=1)
        event = _make_mock_event("e1", "Weekly Sync", recurrence_rules=[rule])
        mock_store.eventWithIdentifier_.return_value = event
        mock_store.saveEvent_span_error_.return_value = (True, None)

        result = cal.edit_event("e1", title="Updated")
        assert result["_action"] == "updated"
        assert result["_span"] == "future"
        mock_store.saveEvent_span_error_.assert_called_with(
            event, mock_eventkit.EKSpanFutureEvents, None
        )
