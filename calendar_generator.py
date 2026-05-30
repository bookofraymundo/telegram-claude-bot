"""
Generate .ics calendar files for Santacruz Brothers LLC bot.
Arizona timezone (MST = UTC-7, no DST).
Default reminders: 1 day before + 1 hour before.
"""
from datetime import datetime


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

    uid = f"{start.strftime('%Y%m%d%H%M%S')}-scbllc@santacruzllc.com"

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
