import geopandas as gpd

# Fix transit stops - convert everything to points
print("Fixing transit stops...")
transit = gpd.read_file("outputs/transit_stops.geojson")
transit["geometry"] = transit.geometry.centroid
transit_clean = transit[["geometry"]].copy()
transit_clean["name"] = transit["name"] if "name" in transit.columns else "Transit Stop"
transit_clean["type"] = "transit"
transit_clean.to_file("outputs/transit_stops_clean.geojson", driver="GeoJSON")
print(f"✅ Transit: {len(transit_clean)} stops saved")

# Fix amenities - convert everything to points
print("Fixing amenities...")
amenities = gpd.read_file("outputs/amenities.geojson")
amenities["geometry"] = amenities.geometry.centroid
amenities_clean = amenities[["geometry", "amenity"]].copy() if "amenity" in amenities.columns else amenities[["geometry"]].copy()
amenities_clean.to_file("outputs/amenities_clean.geojson", driver="GeoJSON")
print(f"✅ Amenities: {len(amenities_clean)} saved")