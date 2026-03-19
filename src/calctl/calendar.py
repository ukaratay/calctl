"""EventKit calendar store access."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from calctl.errors import (
    AccessDeniedError,
    AlarmParseError,
    CalctlError,
    CalendarNotFoundError,
    DateParseError,
    EventNotFoundError,
    EventSaveError,
    RRuleParseError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports for PyObjC (macOS only)
# ---------------------------------------------------------------------------


def _import_eventkit() -> Any:
    import EventKit  # type: ignore[import-untyped]

    return EventKit


def _import_foundation() -> Any:
    import Foundation  # type: ignore[import-untyped]

    return Foundation


def _import_corelocation() -> Any:
    import CoreLocation  # type: ignore[import-untyped]

    return CoreLocation


# ---------------------------------------------------------------------------
# Availability / Status / Participant mappings
# ---------------------------------------------------------------------------

AVAILABILITY_MAP: dict[str, int] = {
    "busy": 0,  # EKEventAvailabilityBusy
    "free": 1,  # EKEventAvailabilityFree
    "tentative": 2,  # EKEventAvailabilityTentative
    "unavailable": 3,  # EKEventAvailabilityUnavailable
}

AVAILABILITY_REVERSE: dict[int, str | None] = {
    -1: None,  # EKEventAvailabilityNotSupported
    0: "busy",
    1: "free",
    2: "tentative",
    3: "unavailable",
}

STATUS_MAP: dict[int, str] = {
    0: "none",
    1: "confirmed",
    2: "tentative",
    3: "canceled",
}

PARTICIPANT_STATUS_MAP: dict[int, str] = {
    0: "unknown",
    1: "pending",
    2: "accepted",
    3: "declined",
    4: "tentative",
    5: "delegated",
    6: "completed",
    7: "in_process",
}

PARTICIPANT_ROLE_MAP: dict[int, str] = {
    0: "unknown",
    1: "required",
    2: "optional",
    3: "chair",
    4: "non_participant",
}

EK_FREQ_MAP: dict[int, str] = {
    0: "DAILY",
    1: "WEEKLY",
    2: "MONTHLY",
    3: "YEARLY",
}

DATEUTIL_FREQ_MAP: dict[int, int] = {}  # filled lazily

RRULE_FREQ_TO_EK: dict[str, int] = {
    "DAILY": 0,
    "WEEKLY": 1,
    "MONTHLY": 2,
    "YEARLY": 3,
}

WEEKDAY_NAMES: list[str] = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_store() -> Any:
    """Get an authorized EKEventStore, requesting access if needed."""
    EventKit = _import_eventkit()
    Foundation = _import_foundation()

    store = EventKit.EKEventStore.alloc().init()
    logger.debug("Requesting calendar access")

    access_result: dict[str, Any] = {"granted": None, "error": None}

    def callback(granted: bool, error: Any) -> None:
        access_result["granted"] = granted
        access_result["error"] = error

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(callback)
    else:
        store.requestAccessToEntityType_completion_(
            EventKit.EKEntityTypeEvent, callback
        )

    timeout = 60
    deadline = time.time() + timeout
    while access_result["granted"] is None and time.time() < deadline:
        remaining = deadline - time.time()
        if remaining < 10:
            logger.warning("Calendar access callback timeout approaching")
        Foundation.NSRunLoop.currentRunLoop().runMode_beforeDate_(
            Foundation.NSDefaultRunLoopMode,
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.25),
        )

    if not access_result["granted"]:
        logger.debug("Calendar access denied")
        msg = (
            "Calendar access denied. "
            "Grant permission in System Settings > Privacy & Security > Calendars."
        )
        raise AccessDeniedError(msg)

    logger.debug("Calendar access granted")
    return store


def _ns_date(date_str: str) -> Any:
    """Parse a date string to NSDate. Supports YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS."""
    Foundation = _import_foundation()
    logger.debug("Parsing date: %s", date_str)

    formatter = Foundation.NSDateFormatter.alloc().init()
    formatter.setTimeZone_(Foundation.NSTimeZone.localTimeZone())

    for fmt in ("yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"):
        formatter.setDateFormat_(fmt)
        d = formatter.dateFromString_(date_str)
        if d is not None:
            return d

    raise DateParseError(
        f"Cannot parse date: {date_str!r}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
    )


def _format_date(ns_date: Any) -> str:
    """Format an NSDate to ISO 8601 string in local timezone."""
    Foundation = _import_foundation()
    formatter = Foundation.NSDateFormatter.alloc().init()
    formatter.setDateFormat_("yyyy-MM-dd'T'HH:mm:ss")
    formatter.setTimeZone_(Foundation.NSTimeZone.localTimeZone())
    return str(formatter.stringFromDate_(ns_date))


def _format_date_optional(ns_date: Any) -> str | None:
    """Format an NSDate or return None if nil."""
    if ns_date is None:
        return None
    return _format_date(ns_date)


def _parse_alarm(spec: str) -> Any:
    """Parse an alarm spec (relative or absolute) and return an EKAlarm."""
    EventKit = _import_eventkit()
    logger.debug("Parsing alarm: %s", spec)

    # Relative: -15m, -1h, -2d
    rel_match = re.fullmatch(r"-(\d+)([mhd])", spec.strip())
    if rel_match:
        n = int(rel_match.group(1))
        unit = rel_match.group(2)
        multipliers = {"m": 60, "h": 3600, "d": 86400}
        offset = -n * multipliers[unit]
        return EventKit.EKAlarm.alarmWithRelativeOffset_(offset)

    # Absolute: ISO datetime
    try:
        ns_date = _ns_date(spec)
        return EventKit.EKAlarm.alarmWithAbsoluteDate_(ns_date)
    except DateParseError:
        pass

    raise AlarmParseError(
        f"Cannot parse alarm: {spec!r}. "
        "Use relative format like -15m, -1h, -2d or ISO datetime."
    )


def _format_alarm(alarm: Any) -> str:
    """Convert an EKAlarm to a string representation."""
    relative_offset = alarm.relativeOffset()
    # relativeOffset returns 0 for absolute alarms; check absoluteDate
    abs_date = alarm.absoluteDate()
    if abs_date is not None:
        return _format_date(abs_date)
    # Relative offset (negative seconds)
    offset_s = int(relative_offset)
    if offset_s == 0:
        return "-0m"
    offset_s = abs(offset_s)
    if offset_s % 86400 == 0:
        return f"-{offset_s // 86400}d"
    if offset_s % 3600 == 0:
        return f"-{offset_s // 3600}h"
    if offset_s % 60 == 0:
        return f"-{offset_s // 60}m"
    return f"-{offset_s}s"


def _parse_geo(geo: str) -> tuple[float, float]:
    """Parse 'lat,lng' string. Raises CalctlError on bad format."""
    parts = geo.split(",")
    if len(parts) != 2:
        raise CalctlError(f"Invalid geo format: {geo!r}. Expected 'lat,lng'.")
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
    except ValueError as exc:
        raise CalctlError(
            f"Invalid geo format: {geo!r}. Lat/lng must be numbers."
        ) from exc
    return lat, lng


def _participant_to_dict(p: Any) -> dict[str, str]:
    """Convert an EKParticipant to a dict."""
    url = p.URL()
    email = str(url.resourceSpecifier()) if url else ""
    status_int = int(p.participantStatus())
    role_int = int(p.participantRole())
    return {
        "name": str(p.name() or ""),
        "email": email,
        "status": PARTICIPANT_STATUS_MAP.get(status_int, "unknown"),
        "role": PARTICIPANT_ROLE_MAP.get(role_int, "unknown"),
    }


def _rrule_to_ek(rrule_str: str) -> Any:
    """Parse an RRULE string and return an EKRecurrenceRule."""
    EventKit = _import_eventkit()
    logger.debug("Parsing RRULE: %s", rrule_str)

    try:
        from dateutil.rrule import rrulestr  # type: ignore[import-untyped]

        rrulestr(rrule_str, ignoretz=True)
    except Exception as exc:
        raise RRuleParseError(f"Invalid RRULE: {rrule_str!r} - {exc}") from exc

    # Extract raw components from the RRULE string directly
    # (dateutil rrule object doesn't expose all components cleanly)
    upper = rrule_str.upper()
    if "RRULE:" in upper:
        upper = upper.split("RRULE:", 1)[1]

    def _get_component(key: str) -> str | None:
        m = re.search(rf"(?:^|;){key}=([^;]+)", upper)
        return m.group(1) if m else None

    freq_str = _get_component("FREQ") or "WEEKLY"
    ek_freq = RRULE_FREQ_TO_EK.get(freq_str)
    if ek_freq is None:
        raise RRuleParseError(f"Unsupported FREQ: {freq_str!r}")

    interval_str = _get_component("INTERVAL")
    interval = int(interval_str) if interval_str else 1

    # Build recurrence end
    recurrence_end = None
    count_str = _get_component("COUNT")
    until_str = _get_component("UNTIL")
    if count_str:
        recurrence_end = EventKit.EKRecurrenceEnd.recurrenceEndWithOccurrenceCount_(
            int(count_str)
        )
    elif until_str:
        # Parse UNTIL date
        until_fmt = until_str.replace("Z", "")
        try:
            until_ns = _ns_date(until_fmt[:10])  # take just date part
        except DateParseError as exc:
            raise RRuleParseError(f"Cannot parse UNTIL: {until_str!r}") from exc
        recurrence_end = EventKit.EKRecurrenceEnd.recurrenceEndWithEndDate_(until_ns)

    # BYDAY
    days_of_week = None
    byday_str = _get_component("BYDAY")
    if byday_str:
        days_of_week = []
        for raw_part in byday_str.split(","):
            part = raw_part.strip()
            # May have ordinal prefix like 1MO, -1FR
            m = re.fullmatch(r"([+-]?\d+)?([A-Z]{2})", part)
            if not m:
                raise RRuleParseError(f"Invalid BYDAY component: {part!r}")
            ordinal_s = m.group(1)
            day_name = m.group(2)
            if day_name not in WEEKDAY_NAMES:
                raise RRuleParseError(f"Unknown weekday: {day_name!r}")
            ek_day = WEEKDAY_NAMES.index(day_name)
            if ordinal_s:
                day_obj = EventKit.EKRecurrenceDayOfWeek.dayOfWeek_weekNumber_(
                    ek_day, int(ordinal_s)
                )
            else:
                day_obj = EventKit.EKRecurrenceDayOfWeek.dayOfWeek_(ek_day)
            days_of_week.append(day_obj)

    # BYMONTHDAY
    days_of_month = None
    bymonthday_str = _get_component("BYMONTHDAY")
    if bymonthday_str:
        days_of_month = [int(d) for d in bymonthday_str.split(",")]

    # BYMONTH
    months_of_year = None
    bymonth_str = _get_component("BYMONTH")
    if bymonth_str:
        months_of_year = [int(m) for m in bymonth_str.split(",")]

    # BYSETPOS
    set_positions = None
    bysetpos_str = _get_component("BYSETPOS")
    if bysetpos_str:
        set_positions = [int(p) for p in bysetpos_str.split(",")]

    return EventKit.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_daysOfTheWeek_daysOfTheMonth_monthsOfTheYear_weeksOfTheYear_daysOfTheYear_setPositions_end_(  # noqa: E501
        ek_freq,
        interval,
        days_of_week,
        days_of_month,
        months_of_year,
        None,  # weeksOfTheYear
        None,  # daysOfTheYear
        set_positions,
        recurrence_end,
    )


def _ek_to_rrule(ek_rule: Any) -> str:
    """Convert an EKRecurrenceRule to an RRULE string."""
    freq_int = int(ek_rule.frequency())
    freq_str = EK_FREQ_MAP.get(freq_int, "WEEKLY")
    parts = [f"FREQ={freq_str}"]

    interval = int(ek_rule.interval())
    if interval > 1:
        parts.append(f"INTERVAL={interval}")

    # BYDAY
    days = ek_rule.daysOfTheWeek()
    if days:
        byday_parts = []
        for d in days:
            day_int = int(d.dayOfTheWeek())
            week_num = int(d.weekNumber())
            day_name = WEEKDAY_NAMES[day_int] if day_int < len(WEEKDAY_NAMES) else "MO"
            if week_num != 0:
                byday_parts.append(f"{week_num}{day_name}")
            else:
                byday_parts.append(day_name)
        parts.append(f"BYDAY={','.join(byday_parts)}")

    # BYMONTHDAY
    dom = ek_rule.daysOfTheMonth()
    if dom:
        parts.append(f"BYMONTHDAY={','.join(str(int(d)) for d in dom)}")

    # BYMONTH
    moy = ek_rule.monthsOfTheYear()
    if moy:
        parts.append(f"BYMONTH={','.join(str(int(m)) for m in moy)}")

    # BYSETPOS
    sp = ek_rule.setPositions()
    if sp:
        parts.append(f"BYSETPOS={','.join(str(int(p)) for p in sp)}")

    # End condition
    end = ek_rule.recurrenceEnd()
    if end is not None:
        end_date = end.endDate()
        end_count = end.occurrenceCount()
        if end_date is not None:
            Foundation = _import_foundation()
            formatter = Foundation.NSDateFormatter.alloc().init()
            formatter.setDateFormat_("yyyyMMdd'T'HHmmss'Z'")
            formatter.setTimeZone_(Foundation.NSTimeZone.timeZoneWithName_("UTC"))
            parts.append(f"UNTIL={formatter.stringFromDate_(end_date)}")
        elif end_count and int(end_count) > 0:
            parts.append(f"COUNT={int(end_count)}")

    return "RRULE:" + ";".join(parts)


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Convert an EKEvent to a JSON-serializable dict with all fields."""
    cal = event.calendar()

    # URL
    url = event.URL()
    url_str = str(url.absoluteString()) if url else ""

    # Geo / structured location
    geo: dict[str, float] | None = None
    struct_loc = event.structuredLocation()
    if struct_loc is not None:
        cl_loc = struct_loc.geoLocation()
        if cl_loc is not None:
            coord = cl_loc.coordinate()
            # PyObjC returns CLLocationCoordinate2D as a tuple (lat, lng)
            if isinstance(coord, tuple):
                geo = {"lat": float(coord[0]), "lng": float(coord[1])}
            else:
                geo = {
                    "lat": float(coord.latitude),
                    "lng": float(coord.longitude),
                }

    # Availability
    avail_int = int(event.availability())
    availability = AVAILABILITY_REVERSE.get(avail_int)

    # Status (read-only)
    status_int = int(event.status())
    status = STATUS_MAP.get(status_int, "none")

    # Organizer (read-only)
    organizer: dict[str, str] | None = None
    org = event.organizer()
    if org is not None:
        org_url = org.URL()
        organizer = {
            "name": str(org.name() or ""),
            "email": str(org_url.resourceSpecifier()) if org_url else "",
        }

    # Attendees (read-only)
    attendees: list[dict[str, str]] = []
    raw_attendees = event.attendees()
    if raw_attendees:
        attendees = [_participant_to_dict(p) for p in raw_attendees]

    # Alarms
    alarms: list[str] = []
    raw_alarms = event.alarms()
    if raw_alarms:
        alarms = [_format_alarm(a) for a in raw_alarms]

    # RRULE
    rrule: str | None = None
    raw_rules = event.recurrenceRules()
    if raw_rules:
        try:
            rrule = _ek_to_rrule(raw_rules[0])
        except Exception:
            logger.debug("Could not serialize recurrence rule", exc_info=True)

    # Timezone
    tz = event.timeZone()
    timezone: str | None = str(tz.name()) if tz is not None else None

    # is_detached
    is_detached = bool(event.isDetached())

    # Created / modified
    created = _format_date_optional(event.creationDate())
    modified = _format_date_optional(event.lastModifiedDate())

    return {
        "id": str(event.eventIdentifier()),
        "title": str(event.title() or ""),
        "start": _format_date(event.startDate()),
        "end": _format_date(event.endDate()),
        "all_day": bool(event.isAllDay()),
        "location": str(event.location() or ""),
        "geo": geo,
        "notes": str(event.notes() or ""),
        "calendar": str(cal.title()) if cal else "Unknown",
        "url": url_str,
        "availability": availability,
        "status": status,
        "organizer": organizer,
        "attendees": attendees,
        "alarms": alarms,
        "rrule": rrule,
        "timezone": timezone,
        "is_detached": is_detached,
        "created": created,
        "modified": modified,
    }


def _apply_alarms(event: Any, alarms: list[str]) -> None:
    """Set alarms on an event, replacing all existing alarms."""
    # Remove existing
    event.setAlarms_(None)
    if not alarms or alarms == [""]:
        return
    parsed = []
    for spec in alarms:
        if spec == "":
            # Clearing mixed with other values — should be caught by CLI but handle here
            continue
        parsed.append(_parse_alarm(spec))
    if parsed:
        event.setAlarms_(parsed)


def _apply_geo(event: Any, geo: str, location: str | None) -> None:
    """Set structured location from geo string. '' clears."""
    EventKit = _import_eventkit()
    CoreLocation = _import_corelocation()

    if geo == "":
        event.setStructuredLocation_(None)
        return

    lat, lng = _parse_geo(geo)
    cl_loc = CoreLocation.CLLocation.alloc().initWithLatitude_longitude_(lat, lng)
    struct_loc = EventKit.EKStructuredLocation.locationWithTitle_(location or "")
    struct_loc.setGeoLocation_(cl_loc)
    event.setStructuredLocation_(struct_loc)


def _span_constant(span: str) -> Any:
    """Map span string to EKSpan constant."""
    EventKit = _import_eventkit()
    if span == "future":
        return EventKit.EKSpanFutureEvents
    return EventKit.EKSpanThisEvent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_calendars() -> list[dict[str, str]]:
    """List all calendars."""
    EventKit = _import_eventkit()
    store = _get_store()
    cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    return [{"name": str(c.title()), "id": str(c.calendarIdentifier())} for c in cals]


def list_events(
    from_date: str,
    to_date: str,
    calendar: str | None = None,
) -> list[dict[str, Any]]:
    """List events in a date range, optionally filtered by calendar name."""
    EventKit = _import_eventkit()
    store = _get_store()

    start = _ns_date(from_date)
    end = _ns_date(to_date)

    # Validate date range
    Foundation = _import_foundation()
    if start.compare_(end) != Foundation.NSOrderedAscending:
        raise DateParseError("Start date must be before end date")

    calendars = None
    if calendar:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        calendars = [c for c in all_cals if str(c.title()).lower() == calendar.lower()]
        if not calendars:
            logger.debug("Calendar %r not found, returning empty list", calendar)
            return []

    logger.debug("Creating predicate for events %s - %s", from_date, to_date)
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start, end, calendars
    )
    events = store.eventsMatchingPredicate_(predicate)
    return [_event_to_dict(e) for e in (events or [])]


def search_events(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    calendar: str | None = None,
) -> list[dict[str, Any]]:
    """Search events by keyword in title, notes, or location."""
    EventKit = _import_eventkit()
    Foundation = _import_foundation()
    store = _get_store()

    now = Foundation.NSDate.date()
    start = (
        _ns_date(from_date) if from_date else now.dateByAddingTimeInterval_(-30 * 86400)
    )
    end = _ns_date(to_date) if to_date else now.dateByAddingTimeInterval_(90 * 86400)

    calendars = None
    if calendar:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        cal_list = [c for c in all_cals if str(c.title()).lower() == calendar.lower()]
        if not cal_list:
            return []
        calendars = cal_list

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start, end, calendars
    )
    events = store.eventsMatchingPredicate_(predicate) or []

    query_lower = query.lower()
    return [
        _event_to_dict(e)
        for e in events
        if query_lower in str(e.title() or "").lower()
        or query_lower in str(e.notes() or "").lower()
        or query_lower in str(e.location() or "").lower()
    ]


def get_event(event_id: str) -> dict[str, Any]:
    """Get a single event by ID."""
    store = _get_store()
    logger.debug("Getting event: %s", event_id)
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        raise EventNotFoundError(f"Event not found: {event_id}")
    return _event_to_dict(event)


def create_event(
    title: str,
    start: str,
    end: str | None = None,
    calendar: str | None = None,
    location: str | None = None,
    geo: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    all_day: bool = False,
    availability: str | None = None,
    timezone: str | None = None,
    rrule: str | None = None,
    alarms: list[str] | None = None,
) -> dict[str, Any]:
    """Create a calendar event."""
    EventKit = _import_eventkit()
    Foundation = _import_foundation()
    store = _get_store()

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setTitle_(title)

    start_ns = _ns_date(start)
    event.setStartDate_(start_ns)

    if all_day:
        event.setAllDay_(True)
        event.setEndDate_(_ns_date(end) if end else start_ns)
    elif end:
        end_ns = _ns_date(end)
        if end_ns.compare_(start_ns) == Foundation.NSOrderedAscending:
            raise DateParseError("End time must be after start time")
        event.setEndDate_(end_ns)
    else:
        event.setEndDate_(start_ns.dateByAddingTimeInterval_(3600))

    if location:
        event.setLocation_(location)

    if geo is not None:
        _apply_geo(event, geo, location)

    if notes:
        event.setNotes_(notes)

    if url:
        Foundation2 = _import_foundation()
        ns_url = Foundation2.NSURL.URLWithString_(url)
        event.setURL_(ns_url)

    if availability is not None:
        if availability not in AVAILABILITY_MAP:
            raise CalctlError(
                f"Invalid availability: {availability!r}. "
                f"Must be one of: {', '.join(AVAILABILITY_MAP)}"
            )
        event.setAvailability_(AVAILABILITY_MAP[availability])

    if timezone:
        Foundation3 = _import_foundation()
        ns_tz = Foundation3.NSTimeZone.timeZoneWithName_(timezone)
        event.setTimeZone_(ns_tz)

    if rrule:
        ek_rule = _rrule_to_ek(rrule)
        event.addRecurrenceRule_(ek_rule)

    if alarms is not None:
        _apply_alarms(event, alarms)

    # Calendar assignment
    if calendar:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        matching = [c for c in all_cals if str(c.title()).lower() == calendar.lower()]
        if not matching:
            raise CalendarNotFoundError(f"Calendar not found: {calendar!r}")
        event.setCalendar_(matching[0])
    else:
        event.setCalendar_(store.defaultCalendarForNewEvents())

    logger.debug("Saving new event: %s", title)
    success, error = store.saveEvent_span_error_(event, EventKit.EKSpanThisEvent, None)
    if not success:
        err_msg = str(error.localizedDescription()) if error else "Unknown error"
        raise EventSaveError(f"Failed to save event: {err_msg}")

    result = _event_to_dict(event)
    result["_action"] = "created"
    return result


def edit_event(
    event_id: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    calendar: str | None = None,
    location: str | None = None,
    geo: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    all_day: bool | None = None,
    availability: str | None = None,
    timezone: str | None = None,
    rrule: str | None = None,
    alarms: list[str] | None = None,
    span: str = "this",
) -> dict[str, Any]:
    """Edit an existing event."""
    EventKit = _import_eventkit()
    Foundation = _import_foundation()
    store = _get_store()

    logger.debug("Getting event to edit: %s", event_id)
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        raise EventNotFoundError(f"Event not found: {event_id}")

    if title is not None:
        event.setTitle_(title)

    if start is not None:
        start_ns = _ns_date(start)
        event.setStartDate_(start_ns)

    if end is not None:
        end_ns = _ns_date(end)
        cur_start = event.startDate()
        if end_ns.compare_(cur_start) == Foundation.NSOrderedAscending:
            raise DateParseError("End time must be after start time")
        event.setEndDate_(end_ns)

    if all_day is not None:
        event.setAllDay_(all_day)

    if location is not None:
        event.setLocation_(location or None)

    if geo is not None:
        _apply_geo(event, geo, location)

    if notes is not None:
        event.setNotes_(notes or None)

    if url is not None:
        if url == "":
            event.setURL_(None)
        else:
            ns_url = Foundation.NSURL.URLWithString_(url)
            event.setURL_(ns_url)

    if availability is not None:
        if availability not in AVAILABILITY_MAP:
            raise CalctlError(
                f"Invalid availability: {availability!r}. "
                f"Must be one of: {', '.join(AVAILABILITY_MAP)}"
            )
        event.setAvailability_(AVAILABILITY_MAP[availability])

    if timezone is not None:
        if timezone == "":
            event.setTimeZone_(None)
        else:
            ns_tz = Foundation.NSTimeZone.timeZoneWithName_(timezone)
            event.setTimeZone_(ns_tz)

    if rrule is not None:
        # Clear existing recurrence rules
        existing_rules = event.recurrenceRules()
        if existing_rules:
            for r in existing_rules:
                event.removeRecurrenceRule_(r)
        if rrule != "":
            ek_rule = _rrule_to_ek(rrule)
            event.addRecurrenceRule_(ek_rule)

    if alarms is not None:
        _apply_alarms(event, alarms)

    if calendar is not None:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        matching = [c for c in all_cals if str(c.title()).lower() == calendar.lower()]
        if not matching:
            raise CalendarNotFoundError(f"Calendar not found: {calendar!r}")
        event.setCalendar_(matching[0])

    ek_span = _span_constant(span)
    logger.debug("Saving edited event: %s (span=%s)", event_id, span)
    success, error = store.saveEvent_span_error_(event, ek_span, None)
    if not success:
        err_msg = str(error.localizedDescription()) if error else "Unknown error"
        raise EventSaveError(f"Failed to edit event: {err_msg}")

    result = _event_to_dict(event)
    result["_action"] = "updated"
    return result


def delete_event(event_id: str, span: str = "this") -> dict[str, Any]:
    """Delete an event by ID."""
    store = _get_store()

    logger.debug("Getting event to delete: %s", event_id)
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        raise EventNotFoundError(f"Event not found: {event_id}")

    details = _event_to_dict(event)
    ek_span = _span_constant(span)

    logger.debug("Deleting event: %s (span=%s)", event_id, span)
    success, error = store.removeEvent_span_error_(event, ek_span, None)
    if not success:
        err_msg = str(error.localizedDescription()) if error else "Unknown error"
        raise EventSaveError(f"Failed to delete event: {err_msg}")

    details["_action"] = "deleted"
    return details
