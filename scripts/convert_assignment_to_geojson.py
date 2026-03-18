import json
import os
import sys
from urllib.request import urlopen, Request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSIGNMENT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment.geojson")

# Change this to the raw GitHub URL for your ward_cells.geojson file
WARD_CELLS_URL = "https://raw.githubusercontent.com/kdidso/gerrymandering-ministering-districts/main/ward_cells.geojson"


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_url(url):
    req = Request(url, headers={"User-Agent": "GitHubActions"})
    with urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_cell_id_field(feature):
    props = feature.get("properties", {})
    candidates = [
        "cell_id",
        "CELL_ID",
        "id",
        "ID",
        "cellid",
        "cellID",
        "grid_id",
        "gridid",
        "OBJECTID",
        "FID"
    ]
    for field in candidates:
        if field in props:
            return field
    return None


def normalize_id(value):
    if value is None:
        return None
    try:
        return str(int(value))
    except Exception:
        return str(value).strip()


def main():
    if not os.path.exists(ASSIGNMENT_PATH):
        raise FileNotFoundError(f"Assignment file not found: {ASSIGNMENT_PATH}")

    assignment_data = load_json_file(ASSIGNMENT_PATH)
    ward_cells_data = load_json_url(WARD_CELLS_URL)

    if assignment_data.get("type") != "district_cell_assignment":
        raise ValueError("district_assignment.json is not in the expected district_cell_assignment format.")

    if ward_cells_data.get("type") != "FeatureCollection":
        raise ValueError("ward_cells.geojson is not a FeatureCollection.")

    ward_features = ward_cells_data.get("features", [])
    if not ward_features:
        raise ValueError("ward_cells.geojson has no features.")

    cell_id_field = detect_cell_id_field(ward_features[0])
    if not cell_id_field:
        raise ValueError("Could not detect the cell ID field in ward_cells.geojson.")

    print(f"Detected cell ID field: {cell_id_field}")

    cell_lookup = {}
    duplicate_ids = set()

    for feature in ward_features:
        props = feature.get("properties", {})
        raw_id = props.get(cell_id_field)
        norm_id = normalize_id(raw_id)

        if norm_id is None:
            continue

        if norm_id in cell_lookup:
            duplicate_ids.add(norm_id)

        cell_lookup[norm_id] = feature

    if duplicate_ids:
        print(f"Warning: found {len(duplicate_ids)} duplicate cell IDs in ward_cells.geojson")

    districts = assignment_data.get("districts", [])
    output_features = []
    missing_cells = []

    for district in districts:
        district_id = district.get("district_id")
        district_color = district.get("district_color")
        cell_ids = district.get("cell_ids", [])

        print(f"Processing district {district_id} with {len(cell_ids)} cells...")

        for cid in cell_ids:
            norm_cid = normalize_id(cid)
            source_feature = cell_lookup.get(norm_cid)

            if not source_feature:
                missing_cells.append({
                    "district_id": district_id,
                    "cell_id": cid
                })
                continue

            output_features.append({
                "type": "Feature",
                "geometry": source_feature.get("geometry"),
                "properties": {
                    **source_feature.get("properties", {}),
                    "district_id": district_id,
                    "district_color": district_color
                }
            })

    output_geojson = {
        "type": "FeatureCollection",
        "features": output_features
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_geojson, f, indent=2)

    print(f"Wrote GeoJSON to: {OUTPUT_PATH}")
    print(f"Output feature count: {len(output_features)}")

    if missing_cells:
        missing_path = os.path.join(REPO_ROOT, "incoming", "district_assignment_missing_cells.json")
        with open(missing_path, "w", encoding="utf-8") as f:
            json.dump(missing_cells, f, indent=2)
        print(f"Missing cell report written to: {missing_path}")
        print(f"Missing cells: {len(missing_cells)}")
    else:
        print("All cell IDs matched successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
