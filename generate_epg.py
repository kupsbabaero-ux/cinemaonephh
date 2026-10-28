import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

SOURCE_URL = "https://www.clickthecity.com/tv/channels/cinema-one"

CHANNEL_ID = "cinema-one-ph"
CHANNEL_NAME = "Cinema One PH"

TIMEZONE = ZoneInfo("Asia/Manila")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_page():
    print("Downloading ClickTheCity page...")

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=30
    )

    print("HTTP status:", response.status_code)
    print("Final URL:", response.url)

    response.raise_for_status()

    if not response.text.strip():
        raise Exception("ClickTheCity returned an empty page.")

    return response.text


def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")

    programs = []

    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)

    # Normalize spaces
    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    # Time patterns:
    # 12:00 AM
    # 1:30 PM
    # 13:30
    time_pattern = re.compile(
        r"^(?P<time>"
        r"(?:0?[1-9]|1[0-2]):[0-5][0-9]\s*(?:AM|PM)"
        r"|"
        r"(?:[01]?[0-9]|2[0-3]):[0-5][0-9]"
        r")"
        r"(?:\s*[-–—]\s*)?"
        r"(?P<title>.+)$",
        re.IGNORECASE
    )

    for line in lines:
        match = time_pattern.match(line)

        if not match:
            continue

        time_part = match.group("time").strip()
        title = match.group("title").strip()

        title = re.sub(r"^[\-–—:|]+", "", title).strip()

        if not title:
            continue

        # Avoid navigation/header junk
        ignored = {
            "cinema one",
            "tv guide",
            "schedule",
            "program schedule",
        }

        if title.lower() in ignored:
            continue

        programs.append({
            "time": time_part,
            "title": title
        })

    # Remove duplicates
    unique = []
    seen = set()

    for program in programs:
        key = (
            program["time"].lower(),
            program["title"].lower()
        )

        if key not in seen:
            seen.add(key)
            unique.append(program)

    return unique


def parse_time(value):
    formats = [
        "%I:%M %p",
        "%I:%M%p",
        "%H:%M",
    ]

    value = value.strip().upper()

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    return None


def create_epg(programs):
    tv = Element(
        "tv",
        {
            "generator-info-name": "Cinema One PH EPG Generator",
            "generator-info-url": SOURCE_URL
        }
    )

    channel = SubElement(
        tv,
        "channel",
        {"id": CHANNEL_ID}
    )

    display_name = SubElement(
        channel,
        "display-name"
    )

    display_name.text = CHANNEL_NAME

    today = datetime.now(TIMEZONE).date()

    for day_offset in range(7):

        current_date = today + timedelta(days=day_offset)

        daily = []

        for program in programs:

            program_time = parse_time(program["time"])

            if program_time is None:
                continue

            start = datetime.combine(
                current_date,
                program_time,
                tzinfo=TIMEZONE
            )

            daily.append({
                "start": start,
                "title": program["title"]
            })

        daily.sort(key=lambda x: x["start"])

        for index, program in enumerate(daily):

            start = program["start"]

            if index + 1 < len(daily):
                stop = daily[index + 1]["start"]
            else:
                stop = datetime.combine(
                    current_date + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=TIMEZONE
                )

            # Prevent invalid duration
            if stop <= start:
                stop = start + timedelta(minutes=30)

            programme = SubElement(
                tv,
                "programme",
                {
                    "start": start.strftime("%Y%m%d%H%M%S %z"),
                    "stop": stop.strftime("%Y%m%d%H%M%S %z"),
                    "channel": CHANNEL_ID
                }
            )

            title = SubElement(
                programme,
                "title",
                {"lang": "en"}
            )

            title.text = program["title"]

            desc = SubElement(
                programme,
                "desc",
                {"lang": "en"}
            )

            desc.text = (
                f"{program['title']} on {CHANNEL_NAME}"
            )

    return tv


def main():

    print("=" * 50)
    print("Cinema One PH EPG Generator")
    print("=" * 50)

    html = get_page()

    print("Parsing schedule...")

    programs = parse_schedule(html)

    print("Programs found:", len(programs))

    if not programs:
        # Save page for debugging
        with open(
            "clickthecity_debug.html",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(html)

        raise Exception(
            "No Cinema One programs found. "
            "clickthecity_debug.html was created."
        )

    print()
    print("Detected programs:")

    for program in programs:
        print(
            f"- {program['time']} | "
            f"{program['title']}"
        )

    print()
    print("Generating 7-day EPG...")

    tv = create_epg(programs)

    indent(tv, space="  ")

    tree = ElementTree(tv)

    tree.write(
        "epg.xml",
        encoding="utf-8",
        xml_declaration=True
    )

    print()
    print("EPG generated successfully.")
    print("File: epg.xml")
    print("Days: 7")


if __name__ == "__main__":
    main()
