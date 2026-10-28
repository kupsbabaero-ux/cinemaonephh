import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree

SOURCE_URL = "https://www.clickthecity.com/tv/channels/cinema-one"

CHANNEL_ID = "cinema-one-ph"
CHANNEL_NAME = "Cinema One PH"

TIMEZONE = ZoneInfo("Asia/Manila")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


def get_schedule():
    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    programs = []

    # ClickTheCity schedule items
    items = soup.select("li")

    for item in items:
        text = item.get_text(" ", strip=True)

        if "–" not in text:
            continue

        parts = text.split("–", 1)

        if len(parts) != 2:
            continue

        time_part = parts[0].strip()
        title = parts[1].strip()

        if not title:
            continue

        if ":" not in time_part:
            continue

        programs.append({
            "time": time_part,
            "title": title
        })

    return programs


def parse_time(time_string):
    formats = [
        "%I:%M %p",
        "%H:%M"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_string, fmt).time()
        except ValueError:
            pass

    return None


def create_epg(programs):
    tv = Element(
        "tv",
        {
            "generator-info-name": "Cinema One PH EPG Generator",
            "generator-info-url": SOURCE_URL
        }
    )

    channel = SubElement(tv, "channel", {"id": CHANNEL_ID})

    display_name = SubElement(channel, "display-name")
    display_name.text = CHANNEL_NAME

    icon = SubElement(channel, "icon")
    icon.set(
        "src",
        "https://www.clickthecity.com/favicon.ico"
    )

    today = datetime.now(TIMEZONE).date()

    # Generate 7 days
    for day_offset in range(7):
        current_date = today + timedelta(days=day_offset)

        parsed = []

        for program in programs:
            t = parse_time(program["time"])

            if t is None:
                continue

            start = datetime.combine(
                current_date,
                t,
                tzinfo=TIMEZONE
            )

            parsed.append({
                "start": start,
                "title": program["title"]
            })

        parsed.sort(key=lambda x: x["start"])

        for index, program in enumerate(parsed):

            start = program["start"]

            if index + 1 < len(parsed):
                stop = parsed[index + 1]["start"]
            else:
                # Last program runs until midnight
                stop = datetime.combine(
                    current_date + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=TIMEZONE
                )

            start_xml = start.strftime("%Y%m%d%H%M%S %z")
            stop_xml = stop.strftime("%Y%m%d%H%M%S %z")

            programme = SubElement(
                tv,
                "programme",
                {
                    "start": start_xml,
                    "stop": stop_xml,
                    "channel": CHANNEL_ID
                }
            )

            title = SubElement(programme, "title", {"lang": "en"})
            title.text = program["title"]

            desc = SubElement(programme, "desc", {"lang": "en"})
            desc.text = f"{program['title']} on {CHANNEL_NAME}"

    return tv


def main():
    print("Getting Cinema One PH schedule...")

    programs = get_schedule()

    if not programs:
        raise Exception(
            "No programs found. ClickTheCity page structure may have changed."
        )

    print(f"Found {len(programs)} programs.")

    tv = create_epg(programs)

    tree = ElementTree(tv)

    tree.write(
        "epg.xml",
        encoding="utf-8",
        xml_declaration=True
    )

    print("EPG generated successfully.")
    print("Output: epg.xml")


if __name__ == "__main__":
    main()
