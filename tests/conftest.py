"""Shared pytest fixtures for calctl tests."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# EventKit / Foundation / CoreLocation mocks
# ---------------------------------------------------------------------------


class _NSComparisonResult:
    """Simulate NSComparisonResult constants."""

    NSOrderedAscending = -1
    NSOrderedSame = 0
    NSOrderedDescending = 1


def _make_ns_date_mock(iso: str) -> MagicMock:
    """Return a MagicMock that pretends to be an NSDate for a given ISO string."""
    m = MagicMock(name=f"NSDate({iso})")
    m._iso = iso

    # compare_ returns NSOrderedAscending when self < other
    def _compare(other: MagicMock) -> int:
        s = getattr(m, "_iso", "")
        o = getattr(other, "_iso", "")
        if s < o:
            return -1
        if s > o:
            return 1
        return 0

    m.compare_ = _compare
    m.dateByAddingTimeInterval_ = lambda secs: _make_ns_date_mock(iso)
    return m


def _make_mock_calendar(name: str = "Work", cal_id: str = "cal-001") -> MagicMock:
    c = MagicMock(name=f"EKCalendar({name})")
    c.title.return_value = name
    c.calendarIdentifier.return_value = cal_id
    return c


def _make_mock_alarm(
    relative_offset: int | None = None, absolute_iso: str | None = None
) -> MagicMock:
    alarm = MagicMock(name="EKAlarm")
    if absolute_iso:
        alarm.absoluteDate.return_value = _make_ns_date_mock(absolute_iso)
        alarm.relativeOffset.return_value = 0.0
    else:
        alarm.absoluteDate.return_value = None
        alarm.relativeOffset.return_value = float(relative_offset or 0)
    return alarm


def _make_mock_recurrence_rule(
    freq: int = 1,  # 1 = WEEKLY
    interval: int = 1,
    days_of_week: list[Any] | None = None,
    days_of_month: list[int] | None = None,
    months_of_year: list[int] | None = None,
    set_positions: list[int] | None = None,
    recurrence_end: Any | None = None,
) -> MagicMock:
    rule = MagicMock(name="EKRecurrenceRule")
    rule.frequency.return_value = freq
    rule.interval.return_value = interval
    rule.daysOfTheWeek.return_value = days_of_week or []
    rule.daysOfTheMonth.return_value = days_of_month
    rule.monthsOfTheYear.return_value = months_of_year
    rule.setPositions.return_value = set_positions
    rule.recurrenceEnd.return_value = recurrence_end
    return rule


def _make_mock_participant(
    name: str = "Alice",
    email: str = "alice@example.com",
    status: int = 2,  # accepted
    role: int = 1,  # required
) -> MagicMock:
    p = MagicMock(name=f"EKParticipant({name})")
    p.name.return_value = name
    url = MagicMock()
    url.resourceSpecifier.return_value = email
    p.URL.return_value = url
    p.participantStatus.return_value = status
    p.participantRole.return_value = role
    return p


def _make_mock_event(
    event_id: str = "evt-001",
    title: str = "Test Meeting",
    start_iso: str = "2026-03-19T10:00:00",
    end_iso: str = "2026-03-19T11:00:00",
    all_day: bool = False,
    location: str = "",
    notes: str = "",
    url_str: str = "",
    calendar_name: str = "Work",
    availability: int = 0,  # busy
    status: int = 1,  # confirmed
    organizer: Any = None,
    attendees: list[Any] | None = None,
    alarms: list[Any] | None = None,
    recurrence_rules: list[Any] | None = None,
    timezone_name: str | None = None,
    is_detached: bool = False,
    created_iso: str | None = "2026-03-18T09:00:00",
    modified_iso: str | None = "2026-03-18T15:00:00",
    struct_location: Any = None,
) -> MagicMock:
    event = MagicMock(name=f"EKEvent({event_id})")
    event.eventIdentifier.return_value = event_id
    event.title.return_value = title
    event.startDate.return_value = _make_ns_date_mock(start_iso)
    event.endDate.return_value = _make_ns_date_mock(end_iso)
    event.isAllDay.return_value = all_day
    event.location.return_value = location or None
    event.notes.return_value = notes or None
    event.structuredLocation.return_value = struct_location
    event.availability.return_value = availability
    event.status.return_value = status
    event.organizer.return_value = organizer
    event.attendees.return_value = attendees or []
    event.alarms.return_value = alarms or []
    event.recurrenceRules.return_value = recurrence_rules or []
    event.isDetached.return_value = is_detached
    event.creationDate.return_value = (
        _make_ns_date_mock(created_iso) if created_iso else None
    )
    event.lastModifiedDate.return_value = (
        _make_ns_date_mock(modified_iso) if modified_iso else None
    )
    event.calendar.return_value = _make_mock_calendar(calendar_name)
    event.timeZone.return_value = None

    if timezone_name:
        tz = MagicMock()
        tz.name.return_value = timezone_name
        event.timeZone.return_value = tz

    if url_str:
        ns_url = MagicMock()
        ns_url.absoluteString.return_value = url_str
        event.URL.return_value = ns_url
    else:
        event.URL.return_value = None

    return event


def _make_mock_store(events: list[Any] | None = None) -> MagicMock:
    """Create a mock EKEventStore."""
    store = MagicMock(name="EKEventStore")
    _events = events or []

    store.calendarsForEntityType_.return_value = [_make_mock_calendar()]
    store.defaultCalendarForNewEvents.return_value = _make_mock_calendar()
    store.eventsMatchingPredicate_.return_value = _events
    store.predicateForEventsWithStartDate_endDate_calendars_.return_value = MagicMock()
    store.eventWithIdentifier_.return_value = _events[0] if _events else None
    store.saveEvent_span_error_.return_value = (True, None)
    store.removeEvent_span_error_.return_value = (True, None)
    return store


def _make_eventkit_module(store: MagicMock) -> MagicMock:
    """Build a mock EventKit module with constants and factory methods."""
    ek = MagicMock(name="EventKit")

    # Constants
    ek.EKEntityTypeEvent = 0
    ek.EKSpanThisEvent = 0
    ek.EKSpanFutureEvents = 1

    # Availability
    ek.EKEventAvailabilityNotSupported = -1
    ek.EKEventAvailabilityBusy = 0
    ek.EKEventAvailabilityFree = 1
    ek.EKEventAvailabilityTentative = 2
    ek.EKEventAvailabilityUnavailable = 3

    # Status
    ek.EKEventStatusNone = 0
    ek.EKEventStatusConfirmed = 1
    ek.EKEventStatusTentative = 2
    ek.EKEventStatusCanceled = 3

    # EKEventStore
    store_class = MagicMock(name="EKEventStore_class")
    store_class.alloc.return_value.init.return_value = store
    ek.EKEventStore = store_class

    # EKEvent factory
    mock_event = _make_mock_event()
    event_class = MagicMock(name="EKEvent_class")
    event_class.eventWithEventStore_.return_value = mock_event
    ek.EKEvent = event_class

    # EKAlarm
    alarm_class = MagicMock(name="EKAlarm_class")
    alarm_class.alarmWithRelativeOffset_.side_effect = lambda offset: _make_mock_alarm(
        relative_offset=int(offset)
    )
    alarm_class.alarmWithAbsoluteDate_.side_effect = lambda d: _make_mock_alarm(
        absolute_iso=getattr(d, "_iso", "2026-01-01T00:00:00")
    )
    ek.EKAlarm = alarm_class

    # EKRecurrenceRule
    rule_class = MagicMock(name="EKRecurrenceRule_class")
    rule_instance = _make_mock_recurrence_rule()
    rule_alloc = MagicMock()
    rule_alloc.initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_.return_value = rule_instance
    rule_class.alloc.return_value = rule_alloc
    ek.EKRecurrenceRule = rule_class

    # EKRecurrenceDayOfWeek
    dow_class = MagicMock(name="EKRecurrenceDayOfWeek_class")

    def _make_dow(day: int) -> MagicMock:
        d = MagicMock(name=f"EKRecurrenceDayOfWeek({day})")
        d.dayOfTheWeek.return_value = day
        d.weekNumber.return_value = 0
        return d

    def _make_dow_with_week(day: int, week: int) -> MagicMock:
        d = MagicMock(name=f"EKRecurrenceDayOfWeek({day},{week})")
        d.dayOfTheWeek.return_value = day
        d.weekNumber.return_value = week
        return d

    dow_class.dayOfWeek_.side_effect = _make_dow
    dow_class.dayOfWeek_weekNumber_.side_effect = _make_dow_with_week
    ek.EKRecurrenceDayOfWeek = dow_class

    # EKRecurrenceEnd
    end_class = MagicMock(name="EKRecurrenceEnd_class")

    def _make_end_count(count: int) -> MagicMock:
        e = MagicMock(name=f"EKRecurrenceEnd(count={count})")
        e.occurrenceCount.return_value = count
        e.endDate.return_value = None
        return e

    def _make_end_date(d: Any) -> MagicMock:
        e = MagicMock(name=f"EKRecurrenceEnd(date)")
        e.endDate.return_value = d
        e.occurrenceCount.return_value = 0
        return e

    end_class.recurrenceEndWithOccurrenceCount_.side_effect = _make_end_count
    end_class.recurrenceEndWithEndDate_.side_effect = _make_end_date
    ek.EKRecurrenceEnd = end_class

    # EKStructuredLocation
    struct_loc_class = MagicMock(name="EKStructuredLocation_class")
    struct_loc_instance = MagicMock(name="EKStructuredLocation_instance")
    struct_loc_class.locationWithTitle_.return_value = struct_loc_instance
    ek.EKStructuredLocation = struct_loc_class

    return ek


def _make_foundation_module() -> MagicMock:
    """Build a mock Foundation module."""
    fd = MagicMock(name="Foundation")

    # NSComparisonResult constants
    fd.NSOrderedAscending = -1
    fd.NSOrderedSame = 0
    fd.NSOrderedDescending = 1
    fd.NSDefaultRunLoopMode = "kCFRunLoopDefaultMode"

    # NSDateFormatter
    formatter = MagicMock(name="NSDateFormatter")
    formatter_instance = MagicMock(name="NSDateFormatter_instance")
    # dateFromString_ returns a mock NSDate based on the string
    formatter_instance.dateFromString_.side_effect = lambda s: _make_ns_date_mock(s)
    formatter_instance.stringFromDate_.side_effect = lambda d: getattr(
        d, "_iso", "2026-01-01T00:00:00"
    )
    formatter.alloc.return_value.init.return_value = formatter_instance
    fd.NSDateFormatter = formatter

    # NSTimeZone
    tz_class = MagicMock(name="NSTimeZone")
    local_tz = MagicMock(name="localTimeZone")
    local_tz.name.return_value = "America/New_York"
    tz_class.localTimeZone.return_value = local_tz
    utc_tz = MagicMock(name="UTC")
    utc_tz.name.return_value = "UTC"
    tz_class.timeZoneWithName_.return_value = MagicMock(name="NamedTZ")
    fd.NSTimeZone = tz_class

    # NSDate
    date_class = MagicMock(name="NSDate")
    now = _make_ns_date_mock("2026-03-19T12:00:00")
    date_class.date.return_value = now
    date_class.dateWithTimeIntervalSinceNow_.return_value = _make_ns_date_mock(
        "2026-03-19T12:00:15"
    )
    fd.NSDate = date_class

    # NSRunLoop
    run_loop = MagicMock(name="NSRunLoop")
    run_loop.currentRunLoop.return_value = MagicMock()
    fd.NSRunLoop = run_loop

    # NSURL
    url_class = MagicMock(name="NSURL")
    url_instance = MagicMock(name="NSURL_instance")
    url_class.URLWithString_.return_value = url_instance
    fd.NSURL = url_class

    return fd


def _make_corelocation_module() -> MagicMock:
    """Build a mock CoreLocation module."""
    cl = MagicMock(name="CoreLocation")
    cl_loc_class = MagicMock(name="CLLocation_class")

    def _make_cl_loc(lat: float, lng: float) -> MagicMock:
        loc = MagicMock(name=f"CLLocation({lat},{lng})")
        coord = MagicMock()
        coord.latitude = lat
        coord.longitude = lng
        loc.coordinate.return_value = coord
        return loc

    cl_loc_class.alloc.return_value.initWithLatitude_longitude_.side_effect = (
        _make_cl_loc
    )
    cl.CLLocation = cl_loc_class
    return cl


@pytest.fixture()
def mock_store() -> MagicMock:
    """A bare mock EKEventStore with no events by default."""
    return _make_mock_store()


@pytest.fixture()
def mock_eventkit(mock_store: MagicMock) -> MagicMock:
    """Return the mock EventKit module (store pre-wired)."""
    return _make_eventkit_module(mock_store)


@pytest.fixture()
def mock_foundation() -> MagicMock:
    """Return the mock Foundation module."""
    return _make_foundation_module()


@pytest.fixture()
def mock_corelocation() -> MagicMock:
    """Return the mock CoreLocation module."""
    return _make_corelocation_module()


@pytest.fixture()
def patched_calendar(
    mock_eventkit: MagicMock,
    mock_foundation: MagicMock,
    mock_corelocation: MagicMock,
    mock_store: MagicMock,
) -> Any:
    """Patch calendar module imports and wire up the access callback automatically."""
    import calctl.calendar as cal_module

    # Make access callback fire immediately on store creation
    original_get_store = cal_module._get_store

    def _instant_store() -> MagicMock:
        return mock_store

    with (
        patch.object(cal_module, "_import_eventkit", return_value=mock_eventkit),
        patch.object(cal_module, "_import_foundation", return_value=mock_foundation),
        patch.object(
            cal_module, "_import_corelocation", return_value=mock_corelocation
        ),
        patch.object(cal_module, "_get_store", side_effect=_instant_store),
    ):
        yield cal_module
