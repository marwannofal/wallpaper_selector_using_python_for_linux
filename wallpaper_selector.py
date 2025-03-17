import sys
import requests
import datetime
import os
import subprocess

API_URL = "https://api.sunrisesunset.io/json"
IMAGE_PATH = "/home/marwan/Desktop/wallpaper_selector/images/"

def get_sun_times(lat, lon):
    """Fetch sunrise and sunset times from the API and convert them to UTC datetime."""
    response = requests.get(API_URL, params={"lat": lat, "lng": lon, "formatted": 1})
    if response.status_code != 200:
        print("Error fetching data from API", file=sys.stderr)
        sys.exit(1)

    data = response.json()["results"]

    # parse sunrise and sunset times as naive datetime objects
    sunrise_time = datetime.datetime.strptime(data["sunrise"], "%I:%M:%S %p").time()
    sunset_time = datetime.datetime.strptime(data["sunset"], "%I:%M:%S %p").time()

    # get today's date in the local timezone
    local_timezone = datetime.timezone(datetime.timedelta(minutes=data["utc_offset"]))
    today_date = datetime.datetime.now(local_timezone).date()

    # combine date and time to create timezone-aware datetime objects
    sunrise_local = datetime.datetime.combine(today_date, sunrise_time, tzinfo=local_timezone)
    sunset_local = datetime.datetime.combine(today_date, sunset_time, tzinfo=local_timezone)

    # convert to UTC
    sunrise_utc = sunrise_local.astimezone(datetime.UTC)
    sunset_utc = sunset_local.astimezone(datetime.UTC)

    return sunrise_utc, sunset_utc

def set_wallpaper(image_name):
    """Set the desktop wallpaper based on the detected environment."""
    wallpaper_path = os.path.join(IMAGE_PATH, image_name)

    try:
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background", "picture-uri",
            f"file://{wallpaper_path}"
        ], check=True)
        print(f"Wallpaper successfully set to {image_name}")
    except subprocess.CalledProcessError:
        print("Failed to set wallpaper. Try setting it manually.")

def determine_wallpaper(lat, lon):
    """Determine wallpaper based on sun position."""
    sunrise_time, sunset_time = get_sun_times(lat, lon)

    # get the current UTC time
    now = datetime.datetime.now(datetime.UTC)

    # calculate the midpoint between sunrise and sunset
    midpoint = sunrise_time + (sunset_time - sunrise_time) / 2

    # determine wallpaper
    if now < sunrise_time or now > sunset_time:
        wallpaper = "night.png"
    elif sunrise_time <= now < sunrise_time + datetime.timedelta(minutes=30):
        wallpaper = "sunrise.png"
    elif sunrise_time + datetime.timedelta(minutes=30) <= now < midpoint:
        wallpaper = "morning.png"
    elif midpoint <= now < sunset_time - datetime.timedelta(minutes=30):
        wallpaper = "noon.png"
    elif sunset_time - datetime.timedelta(minutes=30) <= now < sunset_time:
        wallpaper = "evening.png"
    elif sunset_time - datetime.timedelta(minutes=1) <= now <= sunset_time + datetime.timedelta(minutes=1):
        wallpaper = "sunset.png"
    else:
        wallpaper = "night.png"

    print(wallpaper)
    set_wallpaper(wallpaper)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: ./wallpaper_selector.py <latitude> <longitude>", file=sys.stderr)
        sys.exit(1)

    latitude = float(sys.argv[1])
    longitude = float(sys.argv[2])

    determine_wallpaper(latitude, longitude)
