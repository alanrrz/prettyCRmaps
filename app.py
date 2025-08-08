# School Mini-Maps (PNG) — fixed:
# - Uses your GitHub schools.csv only (no uploads).
# - No “Add at click” prompt.
# - Minimal Leaflet map with a PNG export button.

import csv
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from branca.element import MacroElement, JavascriptLink
from jinja2 import Template

st.set_page_config(page_title="School Mini-Maps (PNG)", layout="wide")

SCHOOLS_CSV = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

@st.cache_data(show_spinner=False)
def load_schools(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    reader = csv.DictReader(r.text.splitlines())
    rows = []
    for row in reader:
        name = row.get("LABEL") or row.get("school_name") or row.get("School") or row.get("NAME")
        lat = row.get("LAT") or row.get("latitude") or row.get("lat")
        lon = row.get("LON") or row.get("longitude") or row.get("lon")
        if not name or not lat or not lon:
            continue
        try:
            rows.append({"name": str(name).strip(), "lat": float(lat), "lon": float(lon)})
        except ValueError:
            continue
    if not rows:
        raise ValueError("CSV must include name + lat/lon columns, e.g. LABEL,LAT,LON.")
    unique = {r["name"]: r for r in rows}
    names = sorted(unique.keys())
    return names, unique

class EasyPrint(MacroElement):
    _template = Template("""
        {% macro script(this, kwargs) %}
            (function(){
              var map = {{this._parent.get_name()}};
              var printer = L.easyPrint({
                  tileLayer: null,
                  sizeModes: ['Current','A4Portrait','A4Landscape'],
                  filename: '{{this.file_name}}',
                  exportOnly: true,
                  hideControlContainer: false
              }).addTo(map);

              var btn = L.control({position: '{{this.position}}'});
              btn.onAdd = function(){
                  var div = L.DomUtil.create('div','leaflet-bar');
                  var a = L.DomUtil.create('a','',div);
                  a.innerHTML = '⤓';
                  a.title = 'Export PNG';
                  a.href = '#';
                  a.style.textAlign = 'center';
                  a.style.width = '30px';
                  a.style.lineHeight = '30px';
                  L.DomEvent.on(a, 'click', function(e){
                      L.DomEvent.stop(e);
                      printer.printMap('CurrentSize', '{{this.file_name}}');
                  });
                  return div;
              };
              btn.addTo(map);
            })();
        {% endmacro %}
    """)
    def __init__(self, file_name="map_export", position="topleft"):
        super().__init__()
        self._name = "EasyPrint"
        self.file_name = file_name
        self.position = position

st.title("School Mini-Maps (PNG)")

# Load once from your repo
names, name_to_row = load_schools(SCHOOLS_CSV)

# Sidebar controls
with st.sidebar:
    school = st.selectbox("Select school", names, index=0)
    zoom = st.slider("Zoom", 12, 19, 16)
    tile_choice = st.selectbox("Basemap", ["Positron (light)", "DarkMatter", "OSM Standard"], index=0)
    show_label = st.checkbox("Show label", value=True)

target = name_to_row[school]
lat, lon = target["lat"], target["lon"]

# Basemap URLs
if tile_choice.startswith("Positron"):
    tiles = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
    attr = "© OpenStreetMap, © CARTO"
elif tile_choice.startswith("DarkMatter"):
    tiles = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
    attr = "© OpenStreetMap, © CARTO"
else:
    tiles = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    attr = "© OpenStreetMap contributors"

# Build map
m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
folium.TileLayer(tiles=tiles, attr=attr, max_zoom=20, name="base").add_to(m)
folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1).add_to(m)
if show_label:
    folium.Marker([lat, lon], tooltip=school).add_to(m)

# Add client-side PNG export
m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
m.add_child(EasyPrint(file_name=school.replace(" ", "_")))

# Render
st_folium(m, height=560, width=None, returned_objects=[])
st.caption("Use the ⤓ button on the map to download a PNG of the current view.")
