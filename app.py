# Minimal School Selector + PNG map export (Leaflet only)
# Loads your schools CSV (GitHub URL), lets you pick a school, shows a minimalist map,
# and adds a client-side "Export PNG" button (Leaflet.easyPrint).

import csv
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from branca.element import MacroElement, JavascriptLink
from jinja2 import Template

st.set_page_config(page_title="School Mini-Maps (PNG)", layout="wide")

DEFAULT_CSV = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

# --- helpers (no pandas) ---
@st.cache_data(show_spinner=False)
def load_schools(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    reader = csv.DictReader(r.text.splitlines())
    rows = []
    for row in reader:
        # accept either LAT/LON or latitude/longitude column names
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
        raise ValueError("CSV must include name + lat/lon columns (e.g., LABEL,LAT,LON or school_name,latitude,longitude).")
    # unique, sorted
    unique = {r["name"]: r for r in rows}
    names = sorted(unique.keys())
    return names, unique

class EasyPrint(MacroElement):
    """Adds Leaflet.easyPrint control for client-side PNG export."""
    _template = Template("""
        {% macro script(this, kwargs) %}
            (function(){
              var map = {{this._parent.get_name()}};
              var printer = L.easyPrint({
                  tileLayer: null,
                  sizeModes: ['A4Portrait','A4Landscape'],
                  filename: '{{this.file_name}}',
                  exportOnly: true,
                  hideControlContainer: false
              }).addTo(map);

              // Add a small custom button that exports current view as PNG
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

# --- UI ---
st.title("School Mini-Maps (PNG)")

src_mode = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
if src_mode == "GitHub CSV":
    csv_url = st.text_input("Raw CSV URL", DEFAULT_CSV)
    names, name_to_row = load_schools(csv_url)
else:
    up = st.file_uploader("Upload schools.csv", type=["csv"])
    if not up:
        st.stop()
    content = up.read().decode("utf-8")
    names, name_to_row = load_schools("data:text/plain," + content)

col1, col2 = st.columns([2,1])
with col1:
    school = st.selectbox("Select school", names, index=0)
    target = name_to_row[school]
    lat, lon = target["lat"], target["lon"]

    c1, c2, c3 = st.columns(3)
    with c1:
        zoom = st.slider("Zoom", 12, 19, 16)
    with c2:
        bw_tiles = st.selectbox("Style", ["Positron (light, B/W)", "DarkMatter (dark)", "OSM Standard"], index=0)
    with c3:
        show_label = st.checkbox("Show label", value=True)

    # tile templates
    if bw_tiles.startswith("Positron"):
        tiles = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
        attr  = "© OpenStreetMap, © CARTO"
    elif bw_tiles.startswith("DarkMatter"):
        tiles = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        attr  = "© OpenStreetMap, © CARTO"
    else:
        tiles = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attr  = "© OpenStreetMap contributors"

    # build map (minimal UI)
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
    folium.TileLayer(tiles=tiles, attr=attr, max_zoom=20, name="base").add_to(m)
    folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1).add_to(m)
    if show_label:
        folium.Marker([lat, lon], tooltip=school).add_to(m)

    # add easyPrint CDN + control
    m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
    m.add_child(EasyPrint(file_name=school.replace(" ","_")))

    st.caption("Use the ⤓ button on the map to download a PNG of the current view.")

    out = st_folium(m, height=520, width=None, returned_objects=[])
with col2:
    st.write("Tips")
    st.write("- Positron is best for black-and-white print.")
    st.write("- Adjust zoom for campus-level detail.")
    st.write("- Toggle label for ultra-minimal look.")
