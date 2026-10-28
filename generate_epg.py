import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree
import re

SOURCE_URL = "https://www.clickthecity.com/tv/channels/cinema-one"
API_URL = "https://www.clickthecity.com/api/tv/channels/cinema-one/schedule"

CHANNEL_ID = "cinema-one-ph"
CHANNEL_NAME = "Cinema One PH"

TIMEZONE = ZoneInfo("Asia/Manila")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def get_schedule():
    """Fetch schedule from ClickTheCity API (site is a React SPA; HTML scrape no longer works)."""
    response = requests.get(API_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if not payload.get("status"):
        raise Exception(
            f"API returned error: {payload.get('message', 'unknown')}"
        )

    data = payload.get("data") or {}
    days = data.get("sched") or []
    logo = (data.get("details") or {}).get("logo") or (
        "https://www.clickthecity.com/img/tv/ch82.png"
    )

    programs = []
    current_year = datetime.now(TIMEZONE).year

    for day in days:
        date_label = (day.get("date") or "").strip()
        entries = day.get("sched") or []
        if not date_label or not entries:
            continue

        day_date = parse_day_label(date_label, current_year)
        if day_date is None:
            print(f"Skipping unparseable date: {date_label!r}")
            continue

        for entry in entries:
            time_str = (entry.get("time") or "").strip()
            title = (entry.get("title") or "").strip()
            if not time_str or not title:
                continue

            t = parse_time(time_str)
            if t is None:
                print(f"Skipping unparseable time: {time_str!r} ({title})")
                continue

            start = datetime.combine(day_date, t, tzinfo=TIMEZONE)
            programs.append({"start": start, "title": title})

    programs.sort(key=lambda p: p["start"])
    return programs, logo


def parse_day_label(label, year):
    """Parse labels like 'Thursday, October 29' or 'Wednesday, October 28'."""
    # Drop weekday if present
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", label).strip()
    for fmt in ("%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(
                cleaned if "%Y" in fmt else f"{cleaned}, {year}",
                fmt if "%Y" in fmt else f"{fmt}, %Y",
            )
            return dt.date()
        except ValueError:
            continue
    return None


def parse_time(time_string):
    formats = [
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
        "%I %p",
    ]
    s = time_string.strip().upper().replace(".", "")
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def create_epg(programs, logo_url):
    tv = Element(
        "tv",
        {
            "generator-info-name": "Cinema One PH EPG Generator",
            "generator-info-url": SOURCE_URL,
        },
    )

    channel = SubElement(tv, "channel", {"id": CHANNEL_ID})
    display_name = SubElement(channel, "display-name")
    display_name.text = CHANNEL_NAME

    icon = SubElement(channel, "icon")
    icon.set("src", logo_url)

    if not programs:
        return tv

    for index, program in enumerate(programs):
        start = program["start"]

        if index + 1 < len(programs):
            stop = programs[index + 1]["start"]
            # Guard against zero/negative duration (duplicate times)
            if stop <= start:
                stop = start + timedelta(hours=2)
        else:
            # Last programme: assume 2 hours (better than forcing midnight
            # when the list may span multiple calendar days)
            stop = start + timedelta(hours=2)

        start_xml = start.strftime("%Y%m%d%H%M%S %z")
        stop_xml = stop.strftime("%Y%m%d%H%M%S %z")

        programme = SubElement(
            tv,
            "programme",
            {
                "start": start_xml,
                "stop": stop_xml,
                "channel": CHANNEL_ID,
            },
        )

        title = SubElement(programme, "title", {"lang": "en"})
        title.text = program["title"]

        desc = SubElement(programme, "desc", {"lang": "en"})
        desc.text = f"{program['title']} on {CHANNEL_NAME}"

    return tv


def main():
    print("Getting Cinema One PH schedule from API...")

    programs, logo = get_schedule()

    if not programs:
        raise Exception(
            "No programs found in API response. "
            "ClickTheCity schedule may be empty or the endpoint changed."
        )

    print(f"Found {len(programs)} programs.")
    for p in programs[:5]:
        print(f"  {p['start'].strftime('%Y-%m-%d %H:%M')}  {p['title']}")
    if len(programs) > 5:
        print(f"  ... and {len(programs) - 5} more")

    tv = create_epg(programs, logo)
    tree = ElementTree(tv)
    tree.write("epg.xml", encoding="utf-8", xml_declaration=True)

    print("EPG generated successfully.")
    print("Output: epg.xml")


if __name__ == "__main__":
    main()
