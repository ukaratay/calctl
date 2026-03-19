"""EventKit calendar store access."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import EventKit  # type: ignore[import-untyped]
import Foundation  # type: ignore[import-untyped]


def _get_store() -> EventKit.EKEventStore:
    """Get an authorized EKEventStore, requesting access if needed."""
    store = EventKit.EKEventStore.alloc().init()

    access_result: dict[str, Any] = {"granted": None, "error": None}

    def callback(granted: bool, error: Any) -> None:
        access_result["granted"] = granted
        access_result["error"] = error

    # macOS 14+ uses requestFullAccessToEventsWithCompletion_
    # macOS 13 and earlier uses requestAccessToEntityType_completion_
    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(callback)
    else:
        store.requestAccessToEntityType_completion_(
            EventKit.EKEntityTypeEvent, callback
        )

    # Poll run loop until callback fires (generous timeout for first-run TCC dialog)
    timeout = 60
    deadline = time.time() + timeout
    while access_result["granted"] is None and time.time() < deadline:
        Foundation.NSRunLoop.currentRunLoop().runMode_beforeDate_(
            Foundation.NSDefaultRunLoopMode,
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.25),
        )

    if not access_result["granted"]:
        _exit_error(
            "Calendar access denied. "
            "Grant permission in System Settings > Privacy & Security > Calendars."
        )

    return store


def _exit_error(msg: str) -> None:
    """Print error JSON and exit."""
    print(json.dumps({"error": msg}))
    sys.exit(1)


def _ns_date(date_str: str) -> Foundation.NSDate:
    """Parse a date string to NSDate. Supports YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS."""
    formatter = Foundation.NSDateFormatter.alloc().init()
    formatter.setTimeZone_(Foundation.NSTimeZone.localTimeZone())

    for fmt in ("yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"):
        formatter.setDateFormat_(fmt)
        d = formatter.dateFromString_(date_str)
        if d is not None:
            return d

    _exit_error(f"Cannot parse date: {date_str}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    raise SystemExit  # unreachable, for type checker


def _format_date(ns_date: Any) -> str:
    """Format an NSDate to ISO 8601 string in local timezone."""
    formatter = Foundation.NSDateFormatter.alloc().init()
    formatter.setDateFormat_("yyyy-MM-dd'T'HH:mm:ss")
    formatter.setTimeZone_(Foundation.NSTimeZone.localTimeZone())
    return str(formatter.stringFromDate_(ns_date))


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Convert an EKEvent to a JSON-serializable dict."""
    cal = event.calendar()
    url = event.URL()
    return {
        "id": str(event.eventIdentifier()),
        "title": str(event.title() or ""),
        "start": _format_date(event.startDate()),
        "end": _format_date(event.endDate()),
        "all_day": bool(event.isAllDay()),
        "location": str(event.location() or ""),
        "notes": str(event.notes() or ""),
        "calendar": str(cal.title()) if cal else "Unknown",
        "url": str(url.absoluteString()) if url else "",
    }


def list_calendars() -> list[dict[str, str]]:
    """List all calendars."""
    store = _get_store()
    cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    return [
        {"name": str(c.title()), "id": str(c.calendarIdentifier())}
        for c in cals
    ]


def list_events(
    from_date: str, to_date: str, calendar: str | None = None
) -> list[dict[str, Any]]:
    """List events in a date range, optionally filtered by calendar name."""
    store = _get_store()
    start = _ns_date(from_date)
    end = _ns_date(to_date)

    calendars = None
    if calendar:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        calendars = [
            c for c in all_cals if str(c.title()).lower() == calendar.lower()
        ]
        if not calendars:
            return []

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start, end, calendars
    )
    events = store.eventsMatchingPredicate_(predicate)
    return [_event_to_dict(e) for e in (events or [])]


def search_events(
    query: str, from_date: str | None = None, to_date: str | None = None
) -> list[dict[str, Any]]:
    """Search events by keyword in title, notes, or location."""
    now = Foundation.NSDate.date()
    start = (
        _ns_date(from_date) if from_date
        else now.dateByAddingTimeInterval_(-30 * 86400)
    )
    end = (
        _ns_date(to_date) if to_date
        else now.dateByAddingTimeInterval_(90 * 86400)
    )

    store = _get_store()
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start, end, None
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
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        return {"error": f"Event not found: {event_id}"}
    return _event_to_dict(event)


def create_event(
    title: str,
    start: str,
    end: str | None = None,
    calendar: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    all_day: bool = False,
) -> dict[str, Any]:
    """Create a calendar event."""
    store = _get_store()

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setTitle_(title)
    event.setStartDate_(_ns_date(start))

    if all_day:
        event.setAllDay_(True)
        # Default end to same day for all-day events
        event.setEndDate_(_ns_date(end) if end else _ns_date(start))
    else:
        if end:
            event.setEndDate_(_ns_date(end))
        else:
            # Default to 1 hour after start
            start_ns = _ns_date(start)
            event.setEndDate_(start_ns.dateByAddingTimeInterval_(3600))

    if location:
        event.setLocation_(location)
    if notes:
        event.setNotes_(notes)

    if calendar:
        all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
        matching = [
            c for c in all_cals if str(c.title()).lower() == calendar.lower()
        ]
        if matching:
            event.setCalendar_(matching[0])
        else:
            return {"error": f"Calendar '{calendar}' not found"}
    else:
        event.setCalendar_(store.defaultCalendarForNewEvents())

    success, error = store.saveEvent_span_error_(
        event, EventKit.EKSpanThisEvent, None
    )
    if success:
        return _event_to_dict(event)
    err_msg = str(error.localizedDescription()) if error else "Unknown error"
    return {"error": f"Failed to save event: {err_msg}"}


def edit_event(
    event_id: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    all_day: bool | None = None,
) -> dict[str, Any]:
    """Edit an existing event."""
    store = _get_store()
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        return {"error": f"Event not found: {event_id}"}

    if title is not None:
        event.setTitle_(title)
    if start is not None:
        event.setStartDate_(_ns_date(start))
    if end is not None:
        event.setEndDate_(_ns_date(end))
    if location is not None:
        event.setLocation_(location)
    if notes is not None:
        event.setNotes_(notes)
    if all_day is not None:
        event.setAllDay_(all_day)

    success, error = store.saveEvent_span_error_(
        event, EventKit.EKSpanThisEvent, None
    )
    if success:
        return _event_to_dict(event)
    err_msg = str(error.localizedDescription()) if error else "Unknown error"
    return {"error": f"Failed to edit event: {err_msg}"}


def delete_event(event_id: str) -> dict[str, Any]:
    """Delete an event by ID. Returns the deleted event details for confirmation."""
    store = _get_store()
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        return {"error": f"Event not found: {event_id}"}

    details = _event_to_dict(event)

    success, error = store.removeEvent_span_error_(
        event, EventKit.EKSpanThisEvent, None
    )
    if success:
        return {"status": "deleted", **details}
    err_msg = str(error.localizedDescription()) if error else "Unknown error"
    return {"error": f"Failed to delete event: {err_msg}"}
