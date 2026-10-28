#!/usr/bin/env python3
"""
Multi-channel EPG generator (ClickTheCity)
Channels:
  - Cinema One PH  https://www.clickthecity.com/tv/channels/cinema-one
  - ANC PH         https://www.clickthecity.com/tv/channels/anc
  - ANC Global     https://www.clickthecity.com/tv/channels/anc  (same CTC feed)
  - TV5            https://www.clickthecity.com/tv/channels/tv5
  - A2Z            https://www.clickthecity.com/tv/channels/a2z-channel-11
"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import re

TIMEZONE = ZoneInfo("Asia/Manila")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Do not remove any channel — keep all requested
CHANNELS = [
    {
        "id": "cinema-one-ph",
        "names": ["Cinema One PH", "Cinema One"],
        "slug": "cinema-one",
        "page": "https://www.clickthecity.com/tv/channels/cinema-one",
        "logo": "https://www.clickthecity.com/img/tv/ch82.png",
        "category": "Movie",
    },
    {
        "id": "anc-ph",
        "names": ["ANC PH", "ANC", "ABS-CBN News Channel"],
        "slug": "anc",
        "page": "https://www.clickthecity.com/tv/channels/anc",
        "logo": "https://www.clickthecity.com/img/tv/ch13.png",
        "category": "News",
    },
    {
        "id": "anc-global",
        "names": ["ANC Global", "ANC International"],
        "slug": "anc",  # ClickTheCity has one ANC feed; used for both PH + Global ids
        "page": "https://www.clickthecity.com/tv/channels/anc",
        "logo": "https://www.clickthecity.com/img/tv/ch13.png",
        "category": "News",
    },
    {
        "id": "tv5-ph",
        "names": ["TV5", "TV 5"],
        "slug": "tv5",
        "page": "https://www.clickthecity.com/tv/channels/tv5",
        "logo": "https://www.clickthecity.com/img/tv/ch5.png",
        "category": "General",
    },
    {
        "id": "a2z-ph",
        "names": ["A2Z", "A2Z Channel 11"],
        "slug": "a2z-channel-11",
        "page": "https://www.clickthecity.com/tv/channels/a2z-channel-11",
        "logo": "https://cdn1.clickthecity.com/wp-content/uploads/2020/10/21172907/a2z-logo-300x300.png",
        "category": "General",
    },
]


def api_url(slug):
    return f"https://www.clickthecity.com/api/tv/channels/{slug}/schedule"


def parse_day_label(label, year):
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
    return dt.strftime("%Y%m%d%H%M%S %z")


def fetch_channel_schedule(channel):
    """Return (programs list, logo_url). programs may be empty if CTC has no data."""
    url = api_url(channel["slug"])
    print(f"  Fetching {channel['names'][0]} ...")
    print(f"    {url}")

    try:
        response = requests.get(
            url,
            headers={**HEADERS, "Referer": channel["page"]},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"    ERROR: {exc}")
        return [], channel["logo"]

    if not payload.get("status"):
        print(f"    API message: {payload.get('message', 'unknown')}")
        return [], channel["logo"]

    data = payload.get("data") or {}
    logo = (data.get("details") or {}).get("logo") or channel["logo"]
    days = data.get("sched") or []
    year = datetime.now(TIMEZONE).year
    programs = []

    for day in days:
        date_label = (day.get("date") or "").strip()
        entries = day.get("sched") or []
        if not date_label:
            continue

        day_date = parse_day_label(date_label, year)
        if day_date is None:
            print(f"    Skipping date: {date_label!r}")
            continue

        for entry in entries:
            time_str = (entry.get("time") or "").strip()
            title = (entry.get("title") or "").strip()
            if not time_str or not title:
                continue
            t = parse_time(time_str)
            if t is None:
                print(f"    Skipping time: {time_str!r} ({title})")
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
    print(f"    Found {len(programs)} programs")
    for p in programs[:5]:
        print(f"      {p['start'].strftime('%Y-%m-%d %H:%M')}  {p['title']}")
    if len(programs) > 5:
        print(f"      ... +{len(programs) - 5} more")
    return programs, logo


def add_channel_element(tv, channel, logo_url):
    ch = SubElement(tv, "channel", {"id": channel["id"]})
    for name in channel["names"]:
        dn = SubElement(ch, "display-name", {"lang": "en"})
        dn.text = name
    SubElement(ch, "icon", {"src": logo_url})
    url = SubElement(ch, "url")
    url.text = channel["page"]


def add_programmes(tv, channel, programs):
    for index, program in enumerate(programs):
        start = program["start"]
        if index + 1 < len(programs):
            stop = programs[index + 1]["start"]
            if stop <= start:
                stop = start + timedelta(hours=1)
        else:
            stop = start + timedelta(hours=1)

        programme = SubElement(
            tv,
            "programme",
            {
                "start": xmltv_time(start),
                "stop": xmltv_time(stop),
                "channel": channel["id"],
            },
        )
        title = SubElement(programme, "title", {"lang": "en"})
        title.text = program["title"]

        desc = SubElement(programme, "desc", {"lang": "en"})
        desc.text = f"{program['title']} on {channel['names'][0]}"

        cat = SubElement(programme, "category", {"lang": "en"})
        cat.text = channel.get("category") or "General"

        if program.get("show_id"):
            ep = SubElement(programme, "episode-num", {"system": "clickthecity"})
            ep.text = program["show_id"]


def write_pretty_xml(tv, path="epg.xml"):
    rough = tostring(tv, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")
    lines = [line for line in pretty.decode("utf-8").splitlines() if line.strip()]
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    else:
        lines.insert(0, '<?xml version="1.0" encoding="UTF-8"?>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    print("Generating multi-channel EPG from ClickTheCity...")
    print(f"Channels: {len(CHANNELS)}")
    print()

    tv = Element("tv")
    tv.set("generator-info-name", "ClickTheCity Multi-Channel EPG Generator")
    tv.set("generator-info-url", "https://www.clickthecity.com/tv/")
    tv.set("source-info-name", "ClickTheCity")
    tv.set("source-info-url", "https://www.clickthecity.com/tv/")

    # Cache by slug so ANC PH + ANC Global only hit API once
    schedule_cache = {}

    channel_results = []
    for channel in CHANNELS:
        slug = channel["slug"]
        if slug not in schedule_cache:
            schedule_cache[slug] = fetch_channel_schedule(channel)
        programs, logo = schedule_cache[slug]
        channel_results.append((channel, programs, logo))

    # Channels first (XMLTV convention)
    for channel, programs, logo in channel_results:
        add_channel_element(tv, channel, logo)

    # Then programmes
    total = 0
    for channel, programs, logo in channel_results:
        add_programmes(tv, channel, programs)
        total += len(programs)

    write_pretty_xml(tv, "epg.xml")

    print()
    print(f"Total programmes: {total}")
    print("EPG generated successfully (formal XMLTV).")
    print("Output: epg.xml")

    empty = [c["names"][0] for c, p, _ in channel_results if not p]
    if empty:
        print(
            "Note: no listings right now for: "
            + ", ".join(empty)
            + " (ClickTheCity empty/unavailable — will fill on next run when data is back)."
        )


if __name__ == "__main__":
    main()
