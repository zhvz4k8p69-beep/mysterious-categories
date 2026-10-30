#!/usr/bin/env python3
"""Export episode categories from Airtable to categories.json for the
Jimmy Akin's Mysterious World app.

Combines two bases, since each tags episodes the other misses:
- MYS Topics (Future Shows table): Number and Final Category.
- Podcast Editorial Calendar (Edit schedule table): Episode Number and
  Mysterious World Category, for MYS-numbered Mysterious World rows. PAT rows
  are the patron releases; those episodes come out later under MYS numbers.

An episode is in a category if either base puts it there. Writes only episode
numbers and category names, nothing else from either base. Run by
.github/workflows/export.yml; needs AIRTABLE_TOKEN (a personal access token
with data.records:read on both bases).

    AIRTABLE_TOKEN=... python3 export_categories.py            # fetch and write
    python3 export_categories.py --records sample.json          # offline test
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

# (base, table, number field, category field, release date field,
#  series field, series record)
SOURCES = [
    # MYS Topics → Future Shows: Number, Final Category, Used
    ("appy6YOqnOGYN6Mfn", "tbl7noVuqpyHDsXef", "fldGHkvwPleb8p8Oz", "fldWGNMe0Ay32COI5",
     "fldftcus0SnPug4rJ", None, None),
    # Podcast Editorial Calendar → Edit schedule: Episode Number,
    # Mysterious World Category, Release Date, Series Title = Jimmy Akin's Mysterious World
    ("appJrXgLWn3yPdvmr", "tblIVlv5ds3jDK02N", "fldtyF3cvAsumva7m", "fldKc1Mhaih6FPW9F",
     "fld6EdEkto0R35SLJ", "fldg6TEyz97fSmZs5", "recVvRmsW3k8NQQhn"),
]

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "categories.json")

# Editorial Calendar names mapped onto the MYS Topics names the app shows.
SAME_AS = {
    "RELIGION & THE BIBLE": "RELIGION",
    "SCIENCE & TECHNOLOGY": "SCIENCE",
    "CRYPTIDS AND MONSTERS": "CRYPTIDS",
    "THE AFTERLIFE": "AFTERLIFE",
    "ALIENS": "UFOS",
    "GOVERNMENT ACTIVITY": "GOVERNMENT",
    "OUTER SPACE": "SPACE PROGRAM",
}

# Every episode released on April 1 is an April Fools episode, tagged or not.
APRIL_FOOLS = "APRIL FOOLS"

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
    """Normalize an episode number: "MYS0232a" -> "232A", "208-1" -> "208.1".
    None for anything else, such as PAT015 or "MYS Special#1"."""
    m = re.fullmatch(r"(?:MYS\s*)?0*(\d+)(?:[.\-](\d+)|([A-Za-z]))?", str(raw).strip(), re.IGNORECASE)
    if not m:
        return None
    if m.group(2):
        return f"{m.group(1)}.{m.group(2)}"
    return m.group(1) + (m.group(3) or "").upper()


def canonical(name):
    name = " ".join(name.split()).upper()
    return SAME_AS.get(name, name)


def display_name(canon):
    return NAME_OVERRIDES.get(canon) or " ".join(w.capitalize() for w in canon.split())


def slug(canon):
    return re.sub(r"[^a-z0-9]+", "-", canon.lower()).strip("-")


def sort_key(key):
    m = re.match(r"(\d+)(.*)", key)
    return (int(m.group(1)), m.group(2))


def fetch_records(token):
    """Yield (number, [category names], release date) from every source,
    following pagination."""
    for base, table, number_field, category_field, date_field, series_field, series_id in SOURCES:
        fields = [number_field, category_field, date_field] + ([series_field] if series_field else [])
        params = [("fields[]", f) for f in fields] + [("returnFieldsByFieldId", "true"), ("pageSize", "100")]
        offset = None
        while True:
            query = params + ([("offset", offset)] if offset else [])
            url = f"https://api.airtable.com/v0/{base}/{table}?{urllib.parse.urlencode(query)}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.load(resp)
            for rec in page.get("records", []):
                f = rec.get("fields", {})
                if series_field and series_id not in (f.get(series_field) or []):
                    continue
                yield f.get(number_field), f.get(category_field) or [], f.get(date_field)
            offset = page.get("offset")
            if not offset:
                break
            time.sleep(0.25)  # Airtable allows 5 requests per second per base


def build(records):
    categories = {}
    episodes = set()
    for number, names, released in records:
        key = episode_key(number) if number else None
        if not key:
            continue
        if released and str(released)[5:10] == "04-01":
            names = list(names) + [APRIL_FOOLS]
        for name in names:
            canon = canonical(name)
            if canon in EXCLUDED:
                continue
            cid = slug(canon)
            entry = categories.setdefault(cid, {"id": cid, "name": display_name(canon), "episodes": set()})
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
    parser.add_argument("--records", help='JSON list of {"number", "categories", "released"} instead of Airtable')
    args = parser.parse_args()

    if args.records:
        with open(args.records) as f:
            records = [(r["number"], r["categories"], r.get("released")) for r in json.load(f)]
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
