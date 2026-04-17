import geopandas as gpd
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
import math
import warnings
warnings.filterwarnings("ignore")

# ── Load data ──────────────────────────────────────────────────────────
print("⏳ Loading data...")
streets = gpd.read_file("outputs/streets_with_slope.geojson")
transit = gpd.read_file("outputs/transit_stops.geojson")
amenities = gpd.read_file("outputs/amenities.geojson")
print(f"✅ Streets: {len(streets)}, Transit: {len(transit)}, Amenities: {len(amenities)}")

# ── Build a graph from street segments ────────────────────────────────
print("⏳ Building street network graph...")
G = nx.Graph()

for _, row in streets.iterrows():
    u = (round(row["start_lat"], 6), round(row["start_lon"], 6))
    v = (round(row["end_lat"],   6), round(row["end_lon"],   6))
    G.add_edge(u, v,
               street_id      = row["StreetID"],
               length_m       = row["length_m"],
               time_child     = row["time_child_slope"],
               time_adult     = row["time_adult_slope"],
               time_elderly   = row["time_elderly_slope"])

print(f"✅ Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ── Helper: find nearest graph node to a point ────────────────────────
def nearest_node(lat, lon):
    nodes = list(G.nodes())
    dists = [math.sqrt((n[0]-lat)**2 + (n[1]-lon)**2) for n in nodes]
    return nodes[np.argmin(dists)]

# ── Helper: compute isochrone polygon ─────────────────────────────────
def make_isochrone(origin_node, weight_col, cutoff_sec):
    """Return a polygon of reachable area within cutoff_sec seconds"""
    lengths = nx.single_source_dijkstra_path_length(
        G, origin_node, cutoff=cutoff_sec, weight=weight_col
    )
    reachable_nodes = list(lengths.keys())
    if len(reachable_nodes) < 3:
        return None
    points = [Point(n[1], n[0]) for n in reachable_nodes]  # lon, lat for geometry
    return MultiPoint(points).convex_hull

# ── Settings ──────────────────────────────────────────────────────────
AGE_GROUPS  = ["child", "adult", "elderly"]
CUTOFFS     = [300, 600]  # 5 min and 10 min in seconds
COLORS      = {"child": "#4FC3F7", "adult": "#81C784", "elderly": "#FF8A65"}
POI_TYPES = {
    "transit":  transit,
    "school":   amenities[amenities["amenity"] == "school"],
    "medical":  amenities[amenities["amenity"].isin(["hospital", "clinic", "pharmacy"])],
    "grocery":  amenities[amenities["amenity"].isin(["convenience", "supermarket", "grocery"])],
}

# ── Generate isochrones for each POI type ─────────────────────────────
print("⏳ Generating isochrones (this takes a moment)...")
all_isochrones = []
area_records   = []

for poi_type, poi_gdf in POI_TYPES.items():
    if len(poi_gdf) == 0:
        print(f"  ⚠️ No {poi_type} POIs found, skipping")
        continue
    print(f"  Processing {poi_type} ({len(poi_gdf)} locations)...")

    # Use centroid for non-point geometries
    poi_gdf = poi_gdf.copy()
    poi_gdf["geometry"] = poi_gdf.geometry.centroid

    for _, poi in poi_gdf.iterrows():
        lat = poi.geometry.y
        lon = poi.geometry.x
        origin = nearest_node(lat, lon)

        for age in AGE_GROUPS:
            for cutoff in CUTOFFS:
                poly = make_isochrone(origin, f"time_{age}", cutoff)
                if poly is None:
                    continue
                area_records.append({
                    "poi_type": poi_type,
                    "age":      age,
                    "minutes":  cutoff // 60,
                    "area_m2":  poly.area * 1e10  # rough conversion from degrees
                })
                all_isochrones.append({
                    "poi_type": poi_type,
                    "age":      age,
                    "minutes":  cutoff // 60,
                    "geometry": poly
                })

iso_gdf = gpd.GeoDataFrame(all_isochrones, crs="EPSG:4326")
iso_gdf.to_file("outputs/isochrones.geojson", driver="GeoJSON")
print(f"✅ Saved {len(iso_gdf)} isochrones to outputs/isochrones.geojson")

# ── Chart 1: Average area covered by age group ────────────────────────
print("⏳ Making charts...")
df = pd.DataFrame(area_records)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("Connectivity Assessment — Bancho District\nAge-Based Walkable Area by POI Type",
             fontsize=14, fontweight="bold")

for idx, mins in enumerate([5, 10]):
    ax = axes[idx]
    sub = df[df["minutes"] == mins]
    pivot = sub.groupby(["poi_type", "age"])["area_m2"].mean().unstack()
    pivot = pivot.reindex(columns=AGE_GROUPS)
    pivot.plot(kind="bar", ax=ax,
               color=[COLORS[a] for a in AGE_GROUPS],
               edgecolor="white", width=0.7)
    ax.set_title(f"{mins}-Minute Walkshed", fontsize=12, fontweight="bold")
    ax.set_xlabel("POI Type")
    ax.set_ylabel("Average Area Covered (relative units)")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.legend(["Child", "Adult", "Elderly"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("outputs/chart_area_by_age.png", dpi=150, bbox_inches="tight")
print("✅ Saved chart_area_by_age.png")

# ── Chart 2: Slope impact — flat vs slope-adjusted ────────────────────
flat_times  = streets[["time_child",       "time_adult",       "time_elderly"]].mean()
slope_times = streets[["time_child_slope", "time_adult_slope", "time_elderly_slope"]].mean()

fig2, ax2 = plt.subplots(figsize=(9, 5))
x = np.arange(3)
w = 0.35
bars1 = ax2.bar(x - w/2, flat_times.values,  w, label="Flat (no slope)", color="#B0BEC5", edgecolor="white")
bars2 = ax2.bar(x + w/2, slope_times.values, w, label="Slope-adjusted",  color=["#4FC3F7","#81C784","#FF8A65"], edgecolor="white")
ax2.set_xticks(x)
ax2.set_xticklabels(["Child", "Adult", "Elderly"])
ax2.set_ylabel("Avg Travel Time per Segment (seconds)")
ax2.set_title("Impact of Slope on Travel Time by Age Group\n(Bancho District)", fontweight="bold")
ax2.legend()
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig("outputs/chart_slope_impact.png", dpi=150, bbox_inches="tight")
print("✅ Saved chart_slope_impact.png")

plt.show()
print("\n🎉 All done! Check your outputs/ folder.")
print("Files ready for ArcGIS: isochrones.geojson, transit_stops.geojson, amenities.geojson")