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
