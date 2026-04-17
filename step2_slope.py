import geopandas as gpd
import numpy as np
import math
import requests
import time

print("⏳ Loading streets...")
streets = gpd.read_file("outputs/streets_with_speeds.geojson")
print(f"✅ Loaded {len(streets)} street segments")

def get_elevations(coords, batch_size=20, pause=2):
    """Fetch elevations with retries and pauses to avoid rate limiting"""
    elevations = [None] * len(coords)
    for i in range(0, len(coords), batch_size):
        batch = coords[i:i+batch_size]
        locations = "|".join([f"{lat},{lon}" for lat, lon in batch])
        url = f"https://api.opentopodata.org/v1/aster30m?locations={locations}"
        for attempt in range(3):  # retry up to 3 times
            try:
                r = requests.get(url, timeout=30)
                data = r.json()
                if "results" in data:
                    for j, result in enumerate(data["results"]):
                        elevations[i+j] = result["elevation"]
                    print(f"  ✅ {min(i+batch_size, len(coords))}/{len(coords)} points")
                    break
                else:
                    print(f"  ⚠️ Batch {i} attempt {attempt+1} failed: {data.get('status','unknown')}, retrying...")
                    time.sleep(5)
            except Exception as e:
                print(f"  ⚠️ Batch {i} attempt {attempt+1} error: {e}, retrying...")
                time.sleep(5)
        time.sleep(pause)  # pause between every batch

    # Fill any remaining None with 0
    elevations = [e if e is not None else 0 for e in elevations]
    return elevations

print("⏳ Fetching start point elevations (this takes ~3-4 mins)...")
start_coords = list(zip(streets["start_lat"], streets["start_lon"]))
start_elevs = get_elevations(start_coords)

print("⏳ Fetching end point elevations...")
end_coords = list(zip(streets["end_lat"], streets["end_lon"]))
end_elevs = get_elevations(end_coords)

streets["elev_start"] = start_elevs
streets["elev_end"]   = end_elevs

# Calculate grade
streets["elev_diff"] = streets["elev_end"] - streets["elev_start"]
streets["grade"]     = (streets["elev_diff"] / streets["length_m"]).clip(-0.3, 0.3)

print(f"\n✅ Slope calculated")
print(f"   Mean grade: {streets['grade'].mean():.4f}")
print(f"   Max grade:  {streets['grade'].max():.4f}")
print(f"   Min grade:  {streets['grade'].min():.4f}")

# Apply Tobler's hiking function
BASE_SPEEDS = {"child": 2.8, "adult": 4.8, "elderly": 3.0}

def tobler_speed(base_kmh, grade):
    return base_kmh * math.exp(-3.5 * abs(grade + 0.05))

for age, base_speed in BASE_SPEEDS.items():
    streets[f"speed_{age}_slope"] = streets["grade"].apply(
        lambda g, s=base_speed: tobler_speed(s, g)
    )
    streets[f"time_{age}_slope"] = (
        streets["length_m"] / (streets[f"speed_{age}_slope"] * 1000 / 3600)
    ).round(1)

cols = ["StreetID", "grade",
        "time_child", "time_child_slope",
        "time_adult", "time_adult_slope",
        "time_elderly", "time_elderly_slope"]
print("\n📊 Flat vs slope-adjusted times (seconds):")
print(streets[cols].head(8).to_string())

streets.to_file("outputs/streets_with_slope.geojson", driver="GeoJSON")
print("\n✅ Saved to outputs/streets_with_slope.geojson")
print("Next step: generate isochrones")