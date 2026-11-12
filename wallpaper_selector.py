import argparse
from bisect import bisect_right
from calendar import isleap
from datetime import UTC, datetime, time, timedelta
from math import acos, cos, degrees, pi, radians, sin
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


IMAGE_PATH = Path(__file__).resolve().parent / "images"
FRAMES_PATH = IMAGE_PATH / "frames-2000"
LEGACY_FRAMES_PATH = IMAGE_PATH / "frames"
FRAME_COUNT = 2000
DAWN_FRAME = 360
SUNRISE_FRAME = 440
SOLAR_NOON_FRAME = 1000
SUNSET_FRAME = 1560
DUSK_FRAME = 1640


def solar_terms(moment):
    """Return the equation of time in minutes and solar declination in radians."""
    # NOAA General Solar Position Calculations, evaluated at the estimated UTC time.
    hour = moment.hour + moment.minute / 60 + moment.second / 3600
    days = 366 if isleap(moment.year) else 365
    year_angle = 2 * pi / days * (moment.timetuple().tm_yday - 1 + (hour - 12) / 24)
    c1, c2, c3 = (cos(n * year_angle) for n in (1, 2, 3))
    s1, s2, s3 = (sin(n * year_angle) for n in (1, 2, 3))
    equation = 229.18 * (
        0.000075 + 0.001868 * c1 - 0.032077 * s1
        - 0.014615 * c2 - 0.040849 * s2
    )
    declination = (
        0.006918 - 0.399912 * c1 + 0.070257 * s1 - 0.006758 * c2
        + 0.000907 * s2 - 0.002697 * c3 + 0.00148 * s3
    )
    return equation, declination


def solar_event(utc_midnight, latitude, longitude, zenith=None, direction=0):
    """Find a solar crossing or the instant of solar noon."""
    base_minutes = 720 - 4 * longitude
    estimate = utc_midnight + timedelta(minutes=base_minutes)
    for _ in range(3):
        equation, declination = solar_terms(estimate)
        minutes = base_minutes - equation
        if zenith is not None:
            crossing = (cos(radians(zenith)) - sin(latitude) * sin(declination)) / (
                cos(latitude) * cos(declination)
            )
            if not -1 <= crossing <= 1:
                return None
            minutes += direction * 4 * degrees(acos(crossing))
        estimate = utc_midnight + timedelta(minutes=minutes)
    return estimate


def frame_number(now, latitude, longitude, zone):
    """Map local solar events to the corresponding frames in the artwork."""
    now = now.astimezone(UTC)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    local_noon = datetime.combine(day, time(hour=12), zone).astimezone(UTC)
    solar_date = (local_noon + timedelta(hours=longitude / 15)).date()
    utc_midnight = datetime.combine(solar_date, time.min, UTC)
    latitude_radians = radians(latitude)

    noon = solar_event(utc_midnight, latitude_radians, longitude)
    sunrise = solar_event(utc_midnight, latitude_radians, longitude, 90.833, -1)
    sunset = solar_event(utc_midnight, latitude_radians, longitude, 90.833, 1)
    if sunrise is None or sunset is None:
        _, declination = solar_terms(noon)
        zenith = abs(latitude_radians - declination)
        return SOLAR_NOON_FRAME if zenith <= radians(90.833) else 0

    dawn = solar_event(utc_midnight, latitude_radians, longitude, 96, -1)
    dusk = solar_event(utc_midnight, latitude_radians, longitude, 96, 1)
    events = (
        (start, 0),
        (dawn, DAWN_FRAME),
        (sunrise, SUNRISE_FRAME),
        (noon, SOLAR_NOON_FRAME),
        (sunset, SUNSET_FRAME),
        (dusk, DUSK_FRAME),
        (end, FRAME_COUNT),
    )
    anchors = [
        (moment, frame)
        for moment, frame in events
        if moment is not None and start <= moment <= end
    ]
    for (before, first), (after, last) in zip(anchors, anchors[1:]):
        if before <= now < after:
            elapsed = (now - before) / (after - before)
            return min(FRAME_COUNT - 1, first + int(elapsed * (last - first)))

    raise ValueError("Could not map the current time to the solar schedule")


def wallpaper_path(frame):
    if FRAMES_PATH.is_dir():
        return FRAMES_PATH / f"frame_{frame:04d}.jpg"

    legacy_frame = frame // 4
    if LEGACY_FRAMES_PATH.is_dir():
        return LEGACY_FRAMES_PATH / f"frame_{legacy_frame:03d}.jpg"

    cutoffs = (100, 142, 212, 289, 359, 420)
    originals = (
        "night.png", "sunrise.png", "morning.png", "noon.png",
        "evening.png", "sunset.png", "night.png",
    )
    return IMAGE_PATH / originals[bisect_right(cutoffs, legacy_frame)]


def set_wallpaper(path):
    """Apply the selected frame in GNOME light and dark modes."""
    schema = "org.gnome.desktop.background"
    uri = path.as_uri()
    changed = False
    for key in ("picture-uri", "picture-uri-dark"):
        current = subprocess.run(
            ["gsettings", "get", schema, key], check=True, capture_output=True, text=True
        ).stdout.strip()
        if current != f"'{uri}'":
            subprocess.run(["gsettings", "set", schema, key, uri], check=True)
            changed = True
    if changed:
        print(f"Wallpaper set to {path}")


def main():
    parser = argparse.ArgumentParser(description="Choose a desktop wallpaper by local solar time.")
    parser.add_argument("latitude", type=float)
    parser.add_argument("longitude", type=float)
    parser.add_argument("--timezone", default="Asia/Amman", help="IANA timezone (default: Asia/Amman)")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected image without applying it")
    args = parser.parse_args()
    if not -90 <= args.latitude <= 90 or not -180 <= args.longitude <= 180:
        parser.error("latitude must be between -90 and 90 and longitude between -180 and 180")

    try:
        zone = ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        parser.error(f"unknown timezone: {args.timezone}")

    frame = frame_number(datetime.now(UTC), args.latitude, args.longitude, zone)
    path = wallpaper_path(frame)
    if not path.is_file():
        parser.exit(1, f"Wallpaper file not found: {path}\n")
    if args.dry_run:
        print(path)
        return
    try:
        set_wallpaper(path)
    except (OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Failed to set GNOME wallpaper: {exc}\n")


if __name__ == "__main__":
    main()
