# restaurant-menu-pipeline
Data engineering pipeline for extracting, standardizing, and analyzing restaurant menus from diverse formats.

## First batch

Collected 15 menus from 15 restaurants on 18 November 2026. The batch contains
five text PDFs, five HTML menu pages, and five menus requiring OCR. Multi-page
image menus are grouped by restaurant, giving 21 original files in total.

Ten menus are assigned to development and five to testing. Every page from a
restaurant stays in the same split. The test menus have been checked for valid
content, but extraction rules and reference dish records have not been created.

- `data/raw/batch_001/` holds original downloads and per-menu download receipts.
- `data/processed/` is reserved for future extracted and cleaned records.
- `data/sources.json` lists the selected sources and fixed development/test split.
- `data/batch_001_manifest.csv` records file paths, source URLs, download times,
  sizes, content types, and SHA-256 fingerprints.
- `data/BATCH_001.md` describes sample coverage and known limitations.

## Download the batch

Use Python 3.10 or newer with the dependencies in `requirements.txt`.

```powershell
python -m pip install -r requirements.txt
python scripts/download_menus.py
```

The downloader verifies PDF text availability and image readability. It saves
the original response bytes and writes a receipt only after every file for a
menu succeeds. Reruns verify existing fingerprints and retry incomplete menus.
Changed source definitions require a new batch to preserve existing snapshots.
Live source URLs may change or disappear, so a future download can differ from
the initial manifest. HTML files contain the page response, with external styles
and images referenced by URL.

The raw downloads and processed outputs are excluded from Git. The source list,
manifest, and code can be versioned. Redistribution licenses for the restaurant
files have not been established. The downloads are local study copies.

## Next step

Build extraction for the ten development menus, starting with selectable PDF
text and HTML, then OCR. Manually checked dish records will provide a reference
for measuring missing dishes, incorrect prices, and duplicate records.
