#!/usr/bin/env python3
"""Export episode categories from Airtable to categories.json for the
Jimmy Akin's Mysterious World app.

Reads the MYS Topics base (Future Shows table): each episode's Number and
Final Category. Writes only episode numbers and category names, nothing else
from the base. Run by .github/workflows/export.yml; needs AIRTABLE_TOKEN
(a personal access token with data.records:read on the MYS Topics base).

    AIRTABLE_TOKEN=... python3 export_categories.py            # fetch and write
    python3 export_categories.py --records sample.json          # offline test
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE_ID = "appy6YOqnOGYN6Mfn"           # MYS Topics
TABLE_ID = "tbl7noVuqpyHDsXef"          # Future Shows
NUMBER_FIELD = "fldGHkvwPleb8p8Oz"      # Number (text: "106", "232A", "208.1")
CATEGORY_FIELD = "fldWGNMe0Ay32COI5"    # Final Category (multiple select)

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "categories.json")

# Categories that describe a show format rather than a topic.
EXCLUDED = {"FEEDBACK", "UPDATES", "MINI MYSTERIES"}

# Display names where simple title case gets it wrong.
NAME_OVERRIDES = {
    "UFOS": "UFOs",
    "PATRONS QUESTIONS": "Patrons’ Questions",
}

# Refuse to publish a file that looks truncated (a bad token, a renamed field).
MIN_EPISODES = 200
MIN_CATEGORIES = 5


def episode_key(raw):
    """Normalize an episode number: "0232a" -> "232A", "208-1" -> "208.1"."""
    m = re.fullmatch(r"0*(\d+)(?:[.\-](\d+)|([A-Za-z]))?", str(raw).strip())
    if not m:
        return None
    if m.group(2):
        return f"{m.group(1)}.{m.group(2)}"
    return m.group(1) + (m.group(3) or "").upper()


def display_name(raw):
    raw = raw.strip().upper()
    return NAME_OVERRIDES.get(raw) or " ".join(w.capitalize() for w in raw.split())


def slug(raw):
    return re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")


def sort_key(key):
    m = re.match(r"(\d+)(.*)", key)
    return (int(m.group(1)), m.group(2))


def fetch_records(token):
    """Yield (number, [category names]) for every record, following pagination."""
    params = [
        ("fields[]", NUMBER_FIELD),
        ("fields[]", CATEGORY_FIELD),
        ("returnFieldsByFieldId", "true"),
        ("pageSize", "100"),
    ]
    offset = None
    while True:
        query = params + ([("offset", offset)] if offset else [])
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}?{urllib.parse.urlencode(query)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.load(resp)
        for rec in page.get("records", []):
            fields = rec.get("fields", {})
            yield fields.get(NUMBER_FIELD), fields.get(CATEGORY_FIELD) or []
        offset = page.get("offset")
        if not offset:
            return


def build(records):
    categories = {}
    episodes = set()
    for number, names in records:
        key = episode_key(number) if number else None
        if not key:
            continue
        for name in names:
            if name.strip().upper() in EXCLUDED:
                continue
            cid = slug(name)
            entry = categories.setdefault(cid, {"id": cid, "name": display_name(name), "episodes": set()})
            entry["episodes"].add(key)
            episodes.add(key)

    if len(episodes) < MIN_EPISODES or len(categories) < MIN_CATEGORIES:
        sys.exit(f"Refusing to publish: only {len(episodes)} episodes in {len(categories)} categories.")

    return {
        "version": 1,
        "categories": [
            {**c, "episodes": sorted(c["episodes"], key=sort_key)}
            for c in sorted(categories.values(), key=lambda c: c["name"])
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", help='JSON list of {"number": ..., "categories": [...]} instead of Airtable')
    args = parser.parse_args()

    if args.records:
        with open(args.records) as f:
            records = [(r["number"], r["categories"]) for r in json.load(f)]
    else:
        token = os.environ.get("AIRTABLE_TOKEN")
        if not token:
            sys.exit("AIRTABLE_TOKEN is not set.")
        records = list(fetch_records(token))

    index = build(records)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    total = len({e for c in index["categories"] for e in c["episodes"]})
    print(f"Wrote {len(index['categories'])} categories covering {total} episodes.")


if __name__ == "__main__":
    main()
