# Mysterious World episode categories

`categories.json` lists the episodes of *Jimmy Akin's Mysterious World* in each
topic category, for the show's iOS app. It's exported hourly from two Airtable
bases (MYS Topics and the Podcast Editorial Calendar) by
`.github/workflows/export.yml`, which runs `export_categories.py`.

Run the workflow by hand from the **Actions** tab to publish a change right away.
The workflow needs the `AIRTABLE_TOKEN` secret: a read-only Airtable token with access
to both bases. Episodes released on April 1 are always listed under April Fools.
