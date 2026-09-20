import os
import re
import json
import time
import requests

URL = "https://certcheck.worldathletics.org/FullList"
BASE = "https://certcheck.worldathletics.org"
IMG_TEMPLATE = BASE + "/OpenDocument/{uuid}"

JSON_PATH = "worldathletics_shoes.json"
IMAGES_DIR = "images"

# How polite to be with the server
SLEEP_BETWEEN_IMAGE_REQ = 0.25  # ~4 req/sec


def fetch_raw_data():
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    html_text = resp.text

    m = re.search(r"var\s+litProductsDataRaw\s*=\s*'(.+?)';", html_text, re.DOTALL)
    if not m:
        raise RuntimeError("litProductsDataRaw not found")

    raw = m.group(1)
    raw = raw.encode("utf-8").decode("unicode_escape")
    data = json.loads(raw)
    return data


def map_disciplines(shoe_disciplines_string: str):
    mapping = {
        "Track": "Track",
        "Jump": "Jumps",
        "Throw": "Throws",
        "Road": "Road & RW",
        "Cross": "Cross",
        "Mountain": "Mountain",
        "Trail": "Trail",
    }
    if not shoe_disciplines_string:
        return []
    parts = shoe_disciplines_string.split("|")
    return [mapping.get(p, p) for p in parts]


def build_output(rows):
    output = []
    for r in rows:
        item = {
            "brand": r.get("manufacturerName"),
            "model": r.get("productName"),
            "approvedFor": map_disciplines(r.get("shoeDisciplines")),

            # EXTRA DATA
            "uuid": r.get("productApplicationuuid"),
            "applicationId": r.get("applicationId"),
            "status": r.get("status"),
            "shoeType": r.get("shoeType"),
            "isDevelopmentShoe": r.get("isDevelopmentShoe"),
            "developmentFlag": r.get("shoeDevelopment"),
            "developmentFrom": r.get("certificationStartDateExp"),
            "developmentTo": r.get("certificationEndDateExp"),
            "releaseDate": r.get("releaseDateExp"),
            "approvedFrom": r.get("shoeApprovedFrom"),
            "imageUuid": r.get("imageDocumentuuid"),
            "imageFilename": r.get("imageFilename"),
            "modelNumber": r.get("modelNumber"),
            "alternativeModelNumbers": r.get("alternativeModelNumbers"),
        }
        output.append(item)
    return output


def _safe_filename(s: str) -> str:
    if not s:
        return ""
    return "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in s)


def load_existing_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_by_uuid(existing_items, new_items):
    """
    Returns (merged_list, added_items)

    - merge by uuid (productApplicationuuid)
    - if a uuid already exists: update its fields with the fresh version
      (so changes to approvedFrom/dev etc. are picked up)
    """
    existing_by_uuid = {it.get("uuid"): it for it in existing_items if it.get("uuid")}
    added = []

    for it in new_items:
        u = it.get("uuid")
        if not u:
            continue

        if u in existing_by_uuid:
            # update in place (keeps any extra fields added later by hand)
            existing_by_uuid[u].update(it)
        else:
            existing_by_uuid[u] = it
            added.append(it)

    merged = list(existing_by_uuid.values())

    # Stable, convenient ordering (brand, then model)
    merged.sort(key=lambda x: ((x.get("brand") or "").lower(), (x.get("model") or "").lower(), (x.get("uuid") or "")))
    return merged, added


def _infer_ext_from_response(r, fallback_name: str):
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "png" in ctype:
        return ".png"
    if "webp" in ctype:
        return ".webp"

    fn = (fallback_name or "").lower()
    if fn.endswith(".jpg") or fn.endswith(".jpeg"):
        return ".jpg"
    if fn.endswith(".png"):
        return ".png"
    if fn.endswith(".webp"):
        return ".webp"
    return ".img"


def _find_existing_image_path(out_dir: str, img_uuid: str):
    """
    Look for an already downloaded file containing that uuid, whatever its name/extension.
    """
    if not img_uuid or not os.path.isdir(out_dir):
        return None

    for name in os.listdir(out_dir):
        if img_uuid in name:
            path = os.path.join(out_dir, name)
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
    return None


def download_missing_images(items, out_dir=IMAGES_DIR, sleep_s=SLEEP_BETWEEN_IMAGE_REQ):
    os.makedirs(out_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
    })

    # count how many have a uuid
    with_uuid = [it for it in items if it.get("imageUuid")]
    total = len(with_uuid)

    downloaded = 0
    already = 0
    failed = 0

    for idx, it in enumerate(with_uuid, start=1):
        img_uuid = it.get("imageUuid")

        # if any file containing the uuid already exists, skip it
        existing = _find_existing_image_path(out_dir, img_uuid)
        if existing:
            already += 1
            continue

        url = IMG_TEMPLATE.format(uuid=img_uuid)
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            failed += 1
            print(f"[{idx}/{total}] fail request {img_uuid}: {e}")
            continue

        if r.status_code != 200:
            failed += 1
            print(f"[{idx}/{total}] fail status {r.status_code} {img_uuid}")
            continue

        ext = _infer_ext_from_response(r, it.get("imageFilename"))

        brand = _safe_filename(it.get("brand") or "UnknownBrand")
        model = _safe_filename(it.get("model") or "UnknownModel")
        filename = f"{brand}__{model}__{img_uuid}{ext}"
        path = os.path.join(out_dir, filename)

        with open(path, "wb") as f:
            f.write(r.content)

        downloaded += 1
        if downloaded % 25 == 0:
            print(f"downloaded {downloaded} new images")

        if sleep_s and sleep_s > 0:
            time.sleep(sleep_s)

    print("\nImages:")
    print(f"  Total with uuid: {total}")
    print(f"  Already present:{already}")
    print(f"  Newly downloaded:{downloaded}")
    print(f"  Failed:         {failed}")


def main():
    # 1) fetch the up-to-date list
    data = fetch_raw_data()
    rows = data["rows"]
    fresh_items = build_output(rows)

    # 2) load the local json
    existing_items = load_existing_json(JSON_PATH)

    # 3) incremental merge
    merged, added = merge_by_uuid(existing_items, fresh_items)

    # 4) save the merged json
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"JSON updated: {JSON_PATH}")
    print(f"  Total shoes in file: {len(merged)}")
    print(f"  Newly added shoes:   {len(added)}")

    # 5) download only the missing images (for all shoes, or just the new ones)
    # For the new ones ONLY, change merged -> added
    download_missing_images(merged, out_dir=IMAGES_DIR)


if __name__ == "__main__":
    main()