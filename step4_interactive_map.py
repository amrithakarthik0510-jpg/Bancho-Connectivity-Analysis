import geopandas as gpd
import folium
import json

print("⏳ Loading data...")
iso = gpd.read_file("outputs/isochrones.geojson")
amenities = gpd.read_file("outputs/amenities_clean.geojson")
transit = gpd.read_file("outputs/transit_stops_clean.geojson")
grocery = gpd.read_file("outputs/grocery_stores.geojson")

m = folium.Map(location=[35.6925, 139.7410], zoom_start=15,
               tiles="CartoDB Voyager", attr=" ",
               zoom_control=False)

# ── Coordinates of POIs outside the network — exclude these ───────────
EXCLUDE_COORDS = [
    (35.69243, 139.746545),
    (35.69251849983688, 139.7465357918283),
    (35.69213447588913, 139.7456313969717),
    (35.6858732, 139.7307233),
]

def is_excluded(lat, lon, threshold=0.0003):
    for elat, elon in EXCLUDE_COORDS:
        if abs(lat - elat) < threshold and abs(lon - elon) < threshold:
            return True
    return False

# ── Build isochrone data as JSON ──────────────────────────────────────
iso_data = []
for _, row in iso.iterrows():
    try:
        iso_data.append({
            "poi_type": row["poi_type"],
            "age": row["age"],
            "minutes": int(row["minutes"]),
            "geometry": row.geometry.__geo_interface__
        })
    except:
        continue

# ── Build marker data as JSON ─────────────────────────────────────────
marker_data = []

schools = amenities[amenities["amenity"] == "school"] if "amenity" in amenities.columns else amenities.iloc[0:0]
medical = amenities[amenities["amenity"].isin(["hospital","clinic","pharmacy"])] if "amenity" in amenities.columns else amenities.iloc[0:0]

for _, row in schools.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    if is_excluded(lat, lon): continue
    marker_data.append({"type": "school", "lat": lat, "lon": lon,
                        "name": str(row.get("name", "School")), "label": "School"})

for _, row in medical.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    if is_excluded(lat, lon): continue
    marker_data.append({"type": "medical", "lat": lat, "lon": lon,
                        "name": str(row.get("name", "Medical")),
                        "label": str(row.get("amenity", "medical")).title()})

for _, row in grocery.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    if is_excluded(lat, lon): continue
    name = str(row.get("name", "Convenience Store"))
    if name == "nan": name = "Convenience Store"
    marker_data.append({"type": "grocery", "lat": lat, "lon": lon,
                        "name": name, "label": "Grocery / Convenience"})

for _, row in transit.iterrows():
    lat, lon = row.geometry.y, row.geometry.x
    if is_excluded(lat, lon): continue
    marker_data.append({"type": "transit", "lat": lat, "lon": lon,
                        "name": str(row.get("name", "Transit Stop")), "label": "Transit Stop"})

control_html = f"""
<script>
var isoData = {json.dumps(iso_data)};
var markerData = {json.dumps(marker_data)};
var activeLayers = {{}};
var markerLayers = {{}};
var markerVisible = {{"transit": true, "school": true, "medical": true, "grocery": true}};
var selectedPoi = {{}};
var selectedAge = {{}};
var selectedMin = {{}};
var map;

var colors = {{"child": "#4FC3F7", "adult": "#66BB6A", "elderly": "#FFA726"}};
var markerIcons = {{"transit": "🚌", "school": "🎓", "medical": "🏥", "grocery": "🛒"}};
var markerColors = {{"transit": "#1565C0", "school": "#F57C00", "medical": "#D32F2F", "grocery": "#388E3C"}};

function getActiveKeys() {{
    var keys = [];
    Object.keys(selectedPoi).forEach(function(poi) {{
        if (!selectedPoi[poi]) return;
        Object.keys(selectedAge).forEach(function(age) {{
            if (!selectedAge[age]) return;
            Object.keys(selectedMin).forEach(function(min) {{
                if (!selectedMin[min]) return;
                keys.push(poi + "_" + age + "_" + min);
            }});
        }});
    }});
    return keys;
}}

function redraw() {{
    Object.values(activeLayers).forEach(function(arr) {{
        arr.forEach(function(l) {{ map.removeLayer(l); }});
    }});
    activeLayers = {{}};

    var keys = getActiveKeys();
    var ageOrder = ["adult", "elderly", "child"];
    var sortedKeys = keys.slice().sort(function(a, b) {{
        var ageA = a.split("_")[1];
        var ageB = b.split("_")[1];
        return ageOrder.indexOf(ageA) - ageOrder.indexOf(ageB);
    }});
    sortedKeys.forEach(function(key) {{
        var parts = key.split("_");
        var poi = parts[0];
        var age = parts[1];
        var min = parseInt(parts[2]);
        var layers = [];
        isoData.forEach(function(d) {{
            if (d.poi_type === poi && d.age === age && d.minutes === min) {{
                var layer = L.geoJSON(d.geometry, {{
                    style: {{
                        fillColor: colors[age],
                        color: colors[age],
                        weight: 2,
                        fillOpacity: age === "child" ? 0.5 : 0.25
                    }}
                }}).addTo(map);
                layers.push(layer);
            }}
        }});
        activeLayers[key] = layers;
    }});
}}

function togglePoi(poi) {{
    selectedPoi[poi] = !selectedPoi[poi];
    var btn = document.getElementById("poi-" + poi);
    if (selectedPoi[poi]) {{
        btn.style.background = "#333";
        btn.style.color = "white";
    }} else {{
        btn.style.background = "#f0f0f0";
        btn.style.color = "#333";
    }}
    redraw();
}}

function toggleAge(age) {{
    selectedAge[age] = !selectedAge[age];
    var btn = document.getElementById("age-" + age);
    if (selectedAge[age]) {{
        btn.style.background = colors[age];
        btn.style.color = "white";
    }} else {{
        btn.style.background = "#f0f0f0";
        btn.style.color = "#333";
    }}
    redraw();
}}

function toggleMin(min) {{
    selectedMin[min] = !selectedMin[min];
    var btn = document.getElementById("min-" + min);
    if (selectedMin[min]) {{
        btn.style.background = "#333";
        btn.style.color = "white";
    }} else {{
        btn.style.background = "#f0f0f0";
        btn.style.color = "#333";
    }}
    redraw();
}}

function clearAll() {{
    selectedPoi = {{}};
    selectedAge = {{}};
    selectedMin = {{}};
    document.querySelectorAll(".sel-btn").forEach(function(b) {{
        b.style.background = "#f0f0f0";
        b.style.color = "#333";
    }});
    Object.values(activeLayers).forEach(function(arr) {{
        arr.forEach(function(l) {{ map.removeLayer(l); }});
    }});
    activeLayers = {{}};
}}

function toggleMarker(type) {{
    markerVisible[type] = !markerVisible[type];
    var btn = document.getElementById("tog-" + type);
    if (markerVisible[type]) {{
        btn.style.background = markerColors[type];
        btn.style.color = "white";
        if (markerLayers[type]) markerLayers[type].forEach(function(m) {{ m.addTo(map); }});
    }} else {{
        btn.style.background = "#f0f0f0";
        btn.style.color = "#aaa";
        if (markerLayers[type]) markerLayers[type].forEach(function(m) {{ map.removeLayer(m); }});
    }}
}}

function drawMarkers() {{
    markerData.forEach(function(d) {{
        if (!markerLayers[d.type]) markerLayers[d.type] = [];
        var icon = L.divIcon({{
            html: '<div style="font-size:16px; text-align:center; line-height:1; background:white; border:2.5px solid ' + markerColors[d.type] + '; border-radius:50%; width:28px; height:28px; display:flex; align-items:center; justify-content:center; box-shadow: 0 2px 6px rgba(0,0,0,0.25);">' + markerIcons[d.type] + '</div>',
            iconSize: [28, 28], iconAnchor: [14, 14], className: ""
        }});
        var marker = L.marker([d.lat, d.lon], {{icon: icon}})
            .bindTooltip("<b>" + d.name + "</b><br>" + d.label)
            .addTo(map);
        markerLayers[d.type].push(marker);
    }});
}}

window.addEventListener("load", function() {{
    setTimeout(function() {{
        var mapKeys = Object.keys(window).filter(function(k) {{ return k.startsWith("map_"); }});
        if (mapKeys.length > 0) {{
            map = window[mapKeys[0]];
            L.control.zoom({{ position: 'bottomright' }}).addTo(map);
        }}
        drawMarkers();
    }}, 1000);
}});
</script>

<div style="position: fixed; top: 10px; right: 10px; z-index: 1000;
     background: white; padding: 12px 16px; border-radius: 12px;
     box-shadow: 0 4px 12px rgba(0,0,0,0.2); font-family: Arial;
     display: flex; flex-direction: column; gap: 8px; min-width: 200px;
     max-width: 230px; font-size: 11px;">

    <div style="display:flex; justify-content:space-between; align-items:center;">
        <b style="font-size:12px; color:#222;">Bancho Connectivity</b>
        <button onclick="clearAll()"
            style="padding:3px 8px; border:none; border-radius:6px; cursor:pointer;
                   background:#ff4444; color:white; font-size:10px; font-weight:bold;">
            ✕ Clear all
        </button>
    </div>

    <div style="font-size:9px; color:#888;">
        Select from each row to layer isochrones
    </div>

    <div style="display:flex; flex-direction:column; gap:4px;">
        <span style="font-weight:bold; color:#555; font-size:10px;">📍 POI TYPE</span>
        <div style="display:flex; gap:4px; flex-wrap:wrap;">
            <button id="poi-transit" class="sel-btn" onclick="togglePoi('transit')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">🚌 Transit</button>
            <button id="poi-school" class="sel-btn" onclick="togglePoi('school')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">🎓 Schools</button>
            <button id="poi-medical" class="sel-btn" onclick="togglePoi('medical')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">🏥 Medical</button>
            <button id="poi-grocery" class="sel-btn" onclick="togglePoi('grocery')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">🛒 Grocery</button>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; gap:4px;">
        <span style="font-weight:bold; color:#555; font-size:10px;">🚶 AGE GROUP</span>
        <div style="display:flex; gap:4px; flex-wrap:wrap;">
            <button id="age-adult" class="sel-btn" onclick="toggleAge('adult')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">Adult</button>
            <button id="age-child" class="sel-btn" onclick="toggleAge('child')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">Child</button>
            <button id="age-elderly" class="sel-btn" onclick="toggleAge('elderly')"
                style="padding:4px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">Elderly</button>
        </div>
    </div>

    <div style="display:flex; flex-direction:column; gap:4px;">
        <span style="font-weight:bold; color:#555; font-size:10px;">⏱ WALK TIME</span>
        <div style="display:flex; gap:4px;">
            <button id="min-5" class="sel-btn" onclick="toggleMin(5)"
                style="padding:4px 14px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">5 min</button>
            <button id="min-10" class="sel-btn" onclick="toggleMin(10)"
                style="padding:4px 14px; border:none; border-radius:6px; cursor:pointer;
                       background:#f0f0f0; color:#333; font-size:10px;">10 min</button>
        </div>
    </div>

    <div style="border-top:1px solid #eee; padding-top:8px;">
        <span style="font-weight:bold; color:#555; font-size:10px;">👁 SHOW/HIDE MARKERS</span>
        <div style="display:flex; gap:4px; margin-top:4px; flex-wrap:wrap;">
            <button id="tog-transit" onclick="toggleMarker('transit')"
                style="padding:3px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#1565C0; color:white; font-size:10px;">🚌</button>
            <button id="tog-school" onclick="toggleMarker('school')"
                style="padding:3px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#F57C00; color:white; font-size:10px;">🎓</button>
            <button id="tog-medical" onclick="toggleMarker('medical')"
                style="padding:3px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#D32F2F; color:white; font-size:10px;">🏥</button>
            <button id="tog-grocery" onclick="toggleMarker('grocery')"
                style="padding:3px 7px; border:none; border-radius:6px; cursor:pointer;
                       background:#388E3C; color:white; font-size:10px;">🛒</button>
        </div>
    </div>

    <div style="border-top:1px solid #eee; padding-top:6px; font-size:9px; color:#888; line-height:1.8;">
        <span style="color:#66BB6A; font-size:11px;">●</span> Adult &nbsp;
        <span style="color:#4FC3F7; font-size:11px;">●</span> Child &nbsp;
        <span style="color:#FFA726; font-size:11px;">●</span> Elderly
    </div>
</div>
"""

m.get_root().html.add_child(folium.Element(control_html))

title_html = """
<div style="position: fixed; top: 10px; left: 10px; z-index: 1000;
     background-color: #1a1a2e; padding: 8px 12px; border-radius: 8px;
     box-shadow: 2px 2px 6px rgba(0,0,0,0.4); font-family: Arial;">
    <b style="font-size:13px; color:white;">Bancho Connectivity Assessment</b><br>
    <span style="font-size:10px; color:#aaa;">Walkable catchment areas by age group & POI type</span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

m.save("outputs/bancho_connectivity_map.html")
print("✅ Saved — open outputs/bancho_connectivity_map.html")
