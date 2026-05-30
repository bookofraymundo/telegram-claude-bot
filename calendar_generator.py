"""
Generate .ics calendar files for Santacruz Brothers LLC bot.
Arizona timezone (MST = UTC-7, no DST).
Default reminders: 1 day before + 1 hour before.
"""
from datetime import datetime


def _make_uid(start: datetime) -> str:
    return f"{start.strftime('%Y%m%d%H%M%S')}-scbllc@santacruzllc.com"


def build_ics(
    title: str,
    start: datetime,
    end: datetime,
    location: str = '',
    description: str = '',
) -> bytes:
    """
    Generate an .ics file and return as bytes.
    start/end should be naive datetimes in MST (UTC-7).
    """
    def fmt(dt: datetime) -> str:
        # Convert MST (UTC-7) to UTC for the ics file
        from datetime import timedelta
        utc = dt + timedelta(hours=7)
        return utc.strftime('%Y%m%dT%H%M%SZ')

    uid = _make_uid(start)

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Santacruz Brothers LLC//Bot//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTART:{fmt(start)}',
        f'DTEND:{fmt(end)}',
        f'SUMMARY:{title}',
    ]

    if location:
        lines.append(f'LOCATION:{location}')
    if description:
        lines.append(f'DESCRIPTION:{description}')

    # 1 day before reminder
    lines += [
        'BEGIN:VALARM',
        'TRIGGER:-P1D',
        'ACTION:DISPLAY',
        f'DESCRIPTION:Reminder: {title}',
        'END:VALARM',
    ]

    # 1 hour before reminder
    lines += [
        'BEGIN:VALARM',
        'TRIGGER:-PT1H',
        'ACTION:DISPLAY',
        f'DESCRIPTION:Reminder: {title}',
        'END:VALARM',
    ]

    lines += ['END:VEVENT', 'END:VCALENDAR']

    return '\r\n'.join(lines).encode('utf-8')


def cancel_ics(title: str, original_start: datetime) -> bytes:
    """Generate a cancellation .ics for an event originally created by the bot."""
    uid = _make_uid(original_start)

    def fmt(dt: datetime) -> str:
        from datetime import timedelta
        utc = dt + timedelta(hours=7)
        return utc.strftime('%Y%m%dT%H%M%SZ')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Santacruz Brothers LLC//Bot//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:CANCEL',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTART:{fmt(original_start)}',
        f'SUMMARY:{title}',
        'STATUS:CANCELLED',
        'SEQUENCE:1',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines).encode('utf-8')


def update_ics(
    title: str,
    original_start: datetime,
    new_start: datetime,
    new_end: datetime,
    location: str = '',
    description: str = '',
) -> bytes:
    """Generate an updated .ics using the original event's UID."""
    uid = _make_uid(original_start)

    def fmt(dt: datetime) -> str:
        from datetime import timedelta
        utc = dt + timedelta(hours=7)
        return utc.strftime('%Y%m%dT%H%M%SZ')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Santacruz Brothers LLC//Bot//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:REQUEST',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTART:{fmt(new_start)}',
        f'DTEND:{fmt(new_end)}',
        f'SUMMARY:{title}',
        'SEQUENCE:1',
    ]
    if location:
        lines.append(f'LOCATION:{location}')
    if description:
        lines.append(f'DESCRIPTION:{description}')

    lines += [
        'BEGIN:VALARM',
        'TRIGGER:-P1D',
        'ACTION:DISPLAY',
        f'DESCRIPTION:Reminder: {title}',
        'END:VALARM',
        'BEGIN:VALARM',
        'TRIGGER:-PT1H',
        'ACTION:DISPLAY',
        f'DESCRIPTION:Reminder: {title}',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines).encode('utf-8')
