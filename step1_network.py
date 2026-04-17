import geopandas as gpd
import pandas as pd
import numpy as np
import osmnx as ox
import networkx as nx
from shapely.geometry import Point
import math

# ── Load team's existing data ──────────────────────────────────────────
print("⏳ Loading team's street network and boundary...")
streets = gpd.read_file("StreetNetwork/StreetNetwork_StreetID.shp")
boundary = gpd.read_file("bancho.geojson").to_crs(epsg=4326)
bancho_poly = boundary.geometry.union_all()

print(f"✅ Street segments loaded: {len(streets)}")
print(f"✅ Boundary loaded, CRS: {boundary.crs}")

# ── Download POIs ──────────────────────────────────────────────────────
print("⏳ Downloading points of interest...")
tags_transit = {"public_transport": "stop_position"}
tags_amenity = {"amenity": ["school", "hospital", "clinic", "pharmacy"]}
tags_shop    = {"shop": ["convenience", "supermarket", "grocery"]}

transit   = ox.features_from_polygon(bancho_poly, tags=tags_transit)
amenities = ox.features_from_polygon(bancho_poly, tags=tags_amenity)
grocery   = ox.features_from_polygon(bancho_poly, tags=tags_shop)

# Convert all geometries to centroids
transit["geometry"]   = transit.geometry.centroid
amenities["geometry"] = amenities.geometry.centroid
grocery["geometry"]   = grocery.geometry.centroid

# Standardize grocery to have amenity column
grocery = grocery.copy()
grocery["amenity"] = grocery["shop"]

# Combine amenities + grocery into one file
all_pois = pd.concat([amenities, grocery], ignore_index=True)
all_pois = gpd.GeoDataFrame(all_pois, crs="EPSG:4326")

print(f"✅ Transit stops: {len(transit)}")
print(f"✅ Schools/medical: {len(amenities)}")
print(f"✅ Grocery/convenience: {len(grocery)}")
print(f"✅ Total amenities: {len(all_pois)}")

# ── Add age-based walking speeds ───────────────────────────────────────
print("⏳ Computing age-based travel times per street segment...")

def tobler_speed(base_kmh, grade):
    return base_kmh * math.exp(-3.5 * abs(grade + 0.05))

BASE_SPEEDS = {"child": 2.8, "adult": 4.8, "elderly": 3.0}

streets_m = streets.to_crs(epsg=6677)
streets["length_m"] = streets_m.geometry.length

for age, speed in BASE_SPEEDS.items():
    streets[f"speed_{age}"] = speed
    streets[f"time_{age}"] = (streets["length_m"] / (speed * 1000 / 3600)).round(1)

print("✅ Age-based travel times added")
print(streets[["StreetID", "SHAPE_Leng", "time_child", "time_adult", "time_elderly"]].head())

# ── Save outputs ───────────────────────────────────────────────────────
streets.to_file("outputs/streets_with_speeds.geojson", driver="GeoJSON")
transit.to_file("outputs/transit_stops.geojson", driver="GeoJSON")
all_pois.to_file("outputs/amenities.geojson", driver="GeoJSON")
grocery[["geometry", "amenity", "name"]].to_file("outputs/grocery_stores.geojson", driver="GeoJSON")

print("\n✅ All saved to outputs/ folder")
print("Next step: add slope data and generate isochrones")