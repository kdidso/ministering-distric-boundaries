import os
import sys
import geopandas as gpd
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment.geojson")
OUTPUT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment_dissolved.geojson")


def normalize_district_id(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return int(float(text))
    except Exception:
        return text


def repair_geometries(gdf):
    gdf = gdf[gdf.geometry.notnull()].copy()

    if gdf.empty:
        return gdf

    print("Initial feature count:", len(gdf))
    print("Initial valid geometry count:", int(gdf.geometry.is_valid.sum()))
    print("Initial invalid geometry count:", int((~gdf.geometry.is_valid).sum()))

    repaired = gdf.copy()

    # First try make_valid
    try:
        repaired["geometry"] = repaired.geometry.make_valid()
        print("Applied geometry.make_valid()")
    except Exception as exc:
        print(f"geometry.make_valid() not available or failed: {exc}")

    # Then use buffer(0) as a fallback cleanup
    try:
        repaired["geometry"] = repaired.geometry.buffer(0)
        print("Applied geometry.buffer(0)")
    except Exception as exc:
        print(f"geometry.buffer(0) failed: {exc}")

    repaired = repaired[repaired.geometry.notnull()].copy()
    repaired = repaired[~repaired.geometry.is_empty].copy()

    print("Post-repair valid geometry count:", int(repaired.geometry.is_valid.sum()))
    print("Post-repair invalid geometry count:", int((~repaired.geometry.is_valid).sum()))

    # Keep only valid geometries after repair
    repaired = repaired[repaired.geometry.is_valid].copy()

    return repaired


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    gdf = gpd.read_file(INPUT_PATH)

    print("Input columns:", list(gdf.columns))
    print("Input feature count:", len(gdf))

    if gdf.empty:
        raise ValueError("Input GeoJSON is empty.")

    if "district_id" not in gdf.columns:
        raise ValueError("Input GeoJSON does not contain a 'district_id' field.")

    if "district_color" not in gdf.columns:
        raise ValueError("Input GeoJSON does not contain a 'district_color' field.")

    gdf = repair_geometries(gdf)

    if gdf.empty:
        raise ValueError("No usable geometries remained after repair.")

    gdf["district_id_norm"] = gdf["district_id"].apply(normalize_district_id)

    unique_ids = sorted(
        [v for v in gdf["district_id_norm"].dropna().unique()],
        key=lambda x: str(x)
    )

    print("Unique normalized district ids:", unique_ids)
    print("Unique district count:", len(unique_ids))

    counts = gdf.groupby("district_id_norm").size().reset_index(name="cell_count")
    print("Counts by district:")
    print(counts.to_string(index=False))

    if len(unique_ids) <= 1:
        raise ValueError(
            "Only one unique district_id was found after geometry repair. "
            "Check the input cell-level GeoJSON."
        )

    dissolved = gdf.dissolve(
        by="district_id_norm",
        aggfunc={
            "district_id": "first",
            "district_color": "first"
        },
        as_index=False
    )

    dissolved = dissolved[dissolved.geometry.notnull()].copy()
    dissolved = dissolved[~dissolved.geometry.is_empty].copy()

    # Repair again after dissolve just to be safe
    dissolved = repair_geometries(dissolved)

    if dissolved.empty:
        raise ValueError("Dissolved output became empty after repair.")

    dissolved["district_id"] = dissolved["district_id_norm"]
    dissolved["district_name"] = dissolved["district_id"].apply(
        lambda x: f"District {int(x) + 1}" if str(x).replace("-", "").isdigit() else f"District {x}"
    )
    dissolved["fill"] = dissolved["district_color"]
    dissolved["stroke"] = dissolved["district_color"]
    dissolved["fill_opacity"] = 0.45
    dissolved["stroke_width"] = 2

    keep_cols = [
        "district_id",
        "district_name",
        "district_color",
        "fill",
        "stroke",
        "fill_opacity",
        "stroke_width",
        "geometry"
    ]
    dissolved = dissolved[[c for c in keep_cols if c in dissolved.columns]]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    dissolved.to_file(OUTPUT_PATH, driver="GeoJSON")

    print("Wrote dissolved GeoJSON to:", OUTPUT_PATH)
    print("Output district feature count:", len(dissolved))
    print("Absolute output path:", os.path.abspath(OUTPUT_PATH))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
