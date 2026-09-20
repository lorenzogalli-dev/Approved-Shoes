# Approved Shoes

Scraper for the **official World Athletics list of approved shoes**
([certcheck.worldathletics.org](https://certcheck.worldathletics.org/FullList)).

It pulls the full catalogue of certified models, stores it as a structured JSON file
and archives one picture per shoe locally.

- 📄 `worldathletics_shoes.json` — one record per model (brand, disciplines, dates, model numbers…)
- 🖼️ `images/` — one photo per model, named `Brand__Model__uuid.ext`

The script is **incremental**: run it again and it refreshes the data and downloads
only what is missing.

---

## Requirements

- Python 3.9+ (tested on 3.12)
- An internet connection

## Setup

Run once, inside the project folder:

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate          # Windows: venv\Scripts\activate
python scrape_shoes.py
```

> **Note:** the first `requests` import takes a few seconds, and the script sleeps
> 0.25 s between images so it does not hammer the server. If it looks stuck, it is
> simply working — don't kill it with `Ctrl+C`.

Typical output:

```
JSON updated: worldathletics_shoes.json
  Total shoes in file: 1019
  Newly added shoes:   0

Images:
  Total with uuid: 1019
  Already present:957
  Newly downloaded:62
  Failed:         0
```

A full run from scratch downloads ~1000 images and takes about 10 minutes.

---

## How it works

1. **Fetch** — downloads the `FullList` page and extracts the `litProductsDataRaw`
   JavaScript variable, which holds the entire catalogue as JSON.
2. **Normalisation** — maps the raw fields onto a readable schema and expands the
   discipline codes (`Track`, `Jump` → `Jumps`, `Road` → `Road & RW`, …).
3. **Incremental merge** — merges the fresh data into `worldathletics_shoes.json`
   keyed by `uuid`: existing models are updated, new ones appended, nothing is ever
   lost. The final list is sorted by brand and model.
4. **Images** — downloads only the missing pictures; any file whose name already
   contains the uuid is skipped, so nothing is fetched twice.

## Record structure

```json
{
  "brand": "361 Degrees",
  "model": "Biospeed Future",
  "approvedFor": ["Track", "Jumps", "Javelin", "Road & RW"],
  "uuid": "D13E4B27-B59C-41FE-A3CF-9AFF6BC96F2E",
  "applicationId": 666,
  "status": "APPROVED",
  "shoeType": "non-Spike",
  "isDevelopmentShoe": false,
  "developmentFlag": "No",
  "developmentFrom": null,
  "developmentTo": null,
  "releaseDate": "2024-03-08",
  "approvedFrom": null,
  "imageUuid": "4C5C3872-0207-46D7-BDB7-412B946117E9",
  "imageFilename": "side view.png",
  "modelNumber": "D24Q2R011M",
  "alternativeModelNumbers": "D24K3R608M,D24Q2R602M"
}
```

## Configuration

The settings live at the top of `scrape_shoes.py`:

| Variable | Default | Description |
|---|---|---|
| `JSON_PATH` | `worldathletics_shoes.json` | Data output file |
| `IMAGES_DIR` | `images` | Destination folder for the images |
| `SLEEP_BETWEEN_IMAGE_REQ` | `0.25` | Pause in seconds between two downloads (~4 req/s) |

To download images for **new models only** instead of all of them, replace
`download_missing_images(merged, ...)` with `download_missing_images(added, ...)` in `main()`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `RuntimeError: litProductsDataRaw not found` | World Athletics changed the page: update the regex in `fetch_raw_data()` |
| `KeyboardInterrupt` in the traceback | Not a bug: `Ctrl+C` was pressed. Run it again and let it finish |
| `fail status 404` lines | That image is no longer available on the server; the run continues |

---

## Notes

Personal / informational project. The data and images belong to World Athletics —
use the script responsibly and don't increase the request rate.
