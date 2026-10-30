# Mysterious World episode categories

`categories.json` lists the episodes of *Jimmy Akin's Mysterious World* in each
topic category, for the show's iOS app. It's exported hourly from Airtable by
`.github/workflows/export.yml`, which runs `export_categories.py`.

Run the workflow by hand from the **Actions** tab to publish a change right away.
The workflow needs the `AIRTABLE_TOKEN` secret: a read-only Airtable token for the
MYS Topics base.
