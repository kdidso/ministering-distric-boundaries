import os
import sys
import geopandas as gpd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment.geojson")
OUTPUT_PATH = os.path.join(REPO_ROOT, "incoming", "district_assignment_dissolved.geojson")


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    gdf = gpd.read_file(INPUT_PATH)

    if gdf.empty:
        raise ValueError("Input GeoJSON is empty.")

    if "district_id" not in gdf.columns:
        raise ValueError("Input GeoJSON does not contain a 'district_id' field.")

    if "district_color" not in gdf.columns:
        raise ValueError("Input GeoJSON does not contain a 'district_color' field.")

    # Keep only valid geometries
    gdf = gdf[gdf.geometry.notnull()].copy()

    if gdf.empty:
        raise ValueError("No valid geometries found in input.")

    # Repair invalid geometries when possible
    gdf["geometry"] = gdf.geometry.make_valid()

    # Dissolve by district_id
    dissolved = gdf.dissolve(
        by="district_id",
        aggfunc={
            "district_color": "first"
        },
        as_index=False
    )

    # Add style properties for downstream use
    dissolved["fill"] = dissolved["district_color"]
    dissolved["stroke"] = dissolved["district_color"]
    dissolved["fill-opacity"] = 0.45
    dissolved["stroke-width"] = 2

    # Optional friendly name
    dissolved["district_name"] = dissolved["district_id"].apply(lambda x: f"District {int(x) + 1}")

    # Keep field order tidy
    desired_cols = [
        "district_id",
        "district_name",
        "district_color",
        "fill",
        "stroke",
        "fill-opacity",
        "stroke-width",
        "geometry"
    ]
    dissolved = dissolved[[c for c in desired_cols if c in dissolved.columns]]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    dissolved.to_file(OUTPUT_PATH, driver="GeoJSON")

    print(f"Wrote dissolved GeoJSON to: {OUTPUT_PATH}")
    print(f"District feature count: {len(dissolved)}")
    print(f"Absolute output path: {os.path.abspath(OUTPUT_PATH)}")
    print(f"Output file exists: {os.path.exists(OUTPUT_PATH)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
