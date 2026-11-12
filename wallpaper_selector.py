import datetime
import subprocess
import sys
from pathlib import Path

import requests


API_URL = "https://api.sunrisesunset.io/json"
IMAGE_PATH = Path(__file__).resolve().parent / "images"


def get_sun_times(lat, lon):
    """Fetch today's sunrise and sunset and convert them to UTC."""
    response = requests.get(
        API_URL,
        params={"lat": lat, "lng": lon, "formatted": 1},
    )
    if response.status_code != 200:
        sys.exit("Error fetching data from API")

    data = response.json()["results"]
    sunrise_time = datetime.datetime.strptime(data["sunrise"], "%I:%M:%S %p").time()
    sunset_time = datetime.datetime.strptime(data["sunset"], "%I:%M:%S %p").time()
    local_timezone = datetime.timezone(datetime.timedelta(minutes=data["utc_offset"]))
    today_date = datetime.datetime.now(local_timezone).date()

    sunrise_local = datetime.datetime.combine(
        today_date, sunrise_time, tzinfo=local_timezone
    )
    sunset_local = datetime.datetime.combine(
        today_date, sunset_time, tzinfo=local_timezone
    )
    return (
        sunrise_local.astimezone(datetime.UTC),
        sunset_local.astimezone(datetime.UTC),
    )


def set_wallpaper(image_name):
    """Set the GNOME wallpaper for both light and dark mode."""
    wallpaper_path = IMAGE_PATH / image_name
    if not wallpaper_path.is_file():
        sys.exit(f"Wallpaper file not found: {wallpaper_path}")

    wallpaper_uri = wallpaper_path.as_uri()
    for key in ("picture-uri", "picture-uri-dark"):
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.background", key, wallpaper_uri],
            check=True,
        )

    print(f"Wallpaper set to {wallpaper_path}")


def determine_wallpaper(lat, lon):
    """Choose a wallpaper based on today's sunrise and sunset."""
    sunrise_time, sunset_time = get_sun_times(lat, lon)
    now = datetime.datetime.now(datetime.UTC)
    midpoint = sunrise_time + (sunset_time - sunrise_time) / 2
    thirty_minutes = datetime.timedelta(minutes=30)
    one_minute = datetime.timedelta(minutes=1)

    if now < sunrise_time or now > sunset_time:
        wallpaper = "night.png"
    elif now < sunrise_time + thirty_minutes:
        wallpaper = "sunrise.png"
    elif now < midpoint:
        wallpaper = "morning.png"
    elif now < sunset_time - thirty_minutes:
        wallpaper = "noon.png"
    elif now < sunset_time:
        wallpaper = "evening.png"
    elif sunset_time - one_minute <= now <= sunset_time + one_minute:
        wallpaper = "sunset.png"
    else:
        wallpaper = "night.png"

    print(wallpaper)
    set_wallpaper(wallpaper)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 wallpaper_selector.py <latitude> <longitude>")

    latitude = float(sys.argv[1])
    longitude = float(sys.argv[2])
    determine_wallpaper(latitude, longitude)