#!/usr/bin/env python3
"""
Cinema One PH EPG generator
Source: https://www.clickthecity.com/tv/channels/cinema-one
(via their JSON API — the page is a React SPA, HTML scrape no longer works)
"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import re

SOURCE_URL = "https://www.clickthecity.com/tv/channels/cinema-one"
API_URL = "https://www.clickthecity.com/api/tv/channels/cinema-one/schedule"

# Keep your original ids + common IPTV-friendly aliases
CHANNEL_ID = "cinema-one-ph"
CHANNEL_NAME = "Cinema One PH"
CHANNEL_NAME_ALT = "Cinema One"
CHANNEL_LOGO_FALLBACK = "https://www.clickthecity.com/img/tv/ch82.png"

TIMEZONE = ZoneInfo("Asia/Manila")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": SOURCE_URL,
}


def get_schedule():
    """Fetch schedule from ClickTheCity API (same site as SOURCE_URL)."""
    response = requests.get(API_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if not payload.get("status"):
        raise Exception(
            f"API returned error: {payload.get('message', 'unknown')}"
        )

    data = payload.get("data") or {}
    days = data.get("sched") or []
    logo = (data.get("details") or {}).get("logo") or CHANNEL_LOGO_FALLBACK

    programs = []
    current_year = datetime.now(TIMEZONE).year

    for day in days:
        date_label = (day.get("date") or "").strip()
        entries = day.get("sched") or []
        if not date_label:
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
            programs.append(
                {
                    "start": start,
                    "title": title,
                    "show_id": str(entry.get("show_id") or ""),
                }
            )

    programs.sort(key=lambda p: p["start"])
    return programs, logo


def parse_day_label(label, year):
    """Parse labels like 'Thursday, October 29'."""
    cleaned = re.sub(r"^[A-Za-z]+,\s*", "", label).strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d", "%b %d"):
        try:
            if "%Y" in fmt:
                dt = datetime.strptime(cleaned, fmt)
            else:
                dt = datetime.strptime(f"{cleaned}, {year}", f"{fmt}, %Y")
            return dt.date()
        except ValueError:
            continue
    return None


def parse_time(time_string):
    formats = ["%I:%M %p", "%I:%M%p", "%H:%M", "%I %p"]
    s = time_string.strip().upper().replace(".", "")
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def xmltv_time(dt):
    """XMLTV datetime: YYYYMMDDHHMMSS ±HHMM"""
    return dt.strftime("%Y%m%d%H%M%S %z")


def create_epg(programs, logo_url):
    """Build formal XMLTV document."""
    tv = Element("tv")
    tv.set("generator-info-name", "Cinema One PH EPG Generator")
    tv.set("generator-info-url", SOURCE_URL)
    tv.set("source-info-name", "ClickTheCity")
    tv.set("source-info-url", SOURCE_URL)

    # --- channel ---
    channel = SubElement(tv, "channel", {"id": CHANNEL_ID})

    dn1 = SubElement(channel, "display-name", {"lang": "en"})
    dn1.text = CHANNEL_NAME

    dn2 = SubElement(channel, "display-name", {"lang": "en"})
    dn2.text = CHANNEL_NAME_ALT

    SubElement(channel, "icon", {"src": logo_url})

    url = SubElement(channel, "url")
    url.text = SOURCE_URL

    # --- programmes ---
    for index, program in enumerate(programs):
        start = program["start"]

        if index + 1 < len(programs):
            stop = programs[index + 1]["start"]
            if stop <= start:
                stop = start + timedelta(hours=2)
        else:
            stop = start + timedelta(hours=2)

        programme = SubElement(
            tv,
            "programme",
            {
                "start": xmltv_time(start),
                "stop": xmltv_time(stop),
                "channel": CHANNEL_ID,
            },
        )

        title = SubElement(programme, "title", {"lang": "en"})
        title.text = program["title"]

        desc = SubElement(programme, "desc", {"lang": "en"})
        desc.text = f"{program['title']} on {CHANNEL_NAME}"

        category = SubElement(programme, "category", {"lang": "en"})
        category.text = "Movie"

        if program.get("show_id"):
            episode = SubElement(programme, "episode-num", {"system": "clickthecity"})
            episode.text = program["show_id"]

    return tv


def write_pretty_xml(tv, path="epg.xml"):
    """Write formal, indented XMLTV file with declaration."""
    rough = tostring(tv, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")

    lines = [
        line
        for line in pretty.decode("utf-8").splitlines()
        if line.strip()
    ]
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    else:
        lines.insert(0, '<?xml version="1.0" encoding="UTF-8"?>')

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    print("Getting Cinema One PH schedule from ClickTheCity API...")
    print(f"Source: {SOURCE_URL}")
    print(f"API:    {API_URL}")

    programs, logo = get_schedule()

    print(f"Found {len(programs)} programs.")
    for p in programs[:10]:
        print(f"  {p['start'].strftime('%Y-%m-%d %H:%M %Z')}  {p['title']}")
    if len(programs) > 10:
        print(f"  ... and {len(programs) - 10} more")

    if not programs:
        print(
            "WARNING: ClickTheCity returned no programme listings right now. "
            "Writing formal channel-only EPG (valid XMLTV). "
            "Schedule will fill in automatically when their data is back."
        )

    tv = create_epg(programs, logo)
    write_pretty_xml(tv, "epg.xml")

    print("EPG generated successfully (formal XMLTV).")
    print("Output: epg.xml")


if __name__ == "__main__":
    main()
