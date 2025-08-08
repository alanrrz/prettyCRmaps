# School locator + draw tools + draggable text labels + PNG export
# Loads your schools CSV from GitHub. Minimal tiles. No heavy geo deps.

import csv
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, MeasureControl
from branca.element import JavascriptLink, MacroElement
from jinja2 import Template

st.set_page_config(page_title="School Mini-Maps (Draw + Labels + PNG)", layout="wide")
DEFAULT_CSV = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

@st.cache_data(show_spinner=False)
def load_schools(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    reader = csv.DictReader(r.text.splitlines())
    rows = []
    for row in reader:
        name = row.get("LABEL") or row.get("school_name") or row.get("NAME")
        lat = row.get("LAT") or row.get("latitude")
        lon = row.get("LON") or row.get("longitude")
        if not name or not lat or not lon:
            continue
        try:
            rows.append({"name": str(name).strip(), "lat": float(lat), "lon": float(lon)})
        except ValueError:
            continue
    if not rows:
        raise ValueError("CSV must include school name + lat/lon columns.")
    unique = {r["name"]: r for r in rows}
    return sorted(unique.keys()), unique

class EasyPrint(MacroElement):
    _template = Template("""
        {% macro script(this, kwargs) %}
        (function(){
          var map = {{this._parent.get_name()}};
          var printer = L.easyPrint({
              tileLayer: null,
              sizeModes: ['CurrentSize'],
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

# session state for custom labels
if "labels" not in st.session_state:
    st.session_state.labels = []  # list of dicts: {lat, lon, text, style, size}

st.title("School Mini-Maps")

# Data source
src = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
if src == "GitHub CSV":
    csv_url = st.text_input("Raw CSV URL", DEFAULT_CSV)
    names, name_map = load_schools(csv_url)
else:
    up = st.file_uploader("Upload schools.csv", type=["csv"])
    if not up:
        st.stop()
    text = up.read().decode("utf-8")
    names, name_map = load_schools("data:text/plain," + text)

left, right = st.columns([2.2, 1])

with left:
    school = st.selectbox("Select school", names)
    lat, lon = name_map[school]["lat"], name_map[school]["lon"]

    c1, c2, c3 = st.columns(3)
    with c1:
        zoom = st.slider("Zoom", 12, 19, 16)
    with c2:
        base = st.selectbox("Style", ["Positron (light)", "DarkMatter", "OSM"], index=0)
    with c3:
        show_school_marker = st.checkbox("Show school marker", value=True)

    # tiles
    if base.startswith("Positron"):
        tiles = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap, © CARTO"
    elif base.startswith("DarkMatter"):
        tiles = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap, © CARTO"
    else:
        tiles = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap contributors"

    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
    folium.TileLayer(tiles=tiles, attr=attr, max_zoom=20, name="base").add_to(m)

    if show_school_marker:
        folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1, tooltip=school).add_to(m)

    # draw tools
    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "rectangle": True,
            "polygon": True,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    # measure (miles)
    m.add_child(MeasureControl(primary_length_unit="miles"))

    # easy print (PNG)
    m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
    m.add_child(EasyPrint(file_name=school.replace(" ", "_")))

    # render existing labels
    for lab in st.session_state.labels:
        style = lab["style"]
        size = lab["size"]
        if style == "Label":
            html = f"<div style='font-weight:700;font-size:{size}px;color:#111;background:rgba(255,255,255,0.8);padding:2px 6px;border:1px solid #111;border-radius:3px'>{lab['text']}</div>"
        elif style == "Outlined":
            html = f"<div style='font-weight:800;font-size:{size}px;color:#111;-webkit-text-stroke:2px #fff;text-shadow:0 0 2px #fff'>{lab['text']}</div>"
        else:  # Filled (orange)
            html = f"<div style='font-weight:800;font-size:{size}px;color:#112;border:2px solid #112;background:#f6a500;padding:4px 8px;border-radius:3px'>{lab['text']}</div>"
        folium.Marker(
            [lab["lat"], lab["lon"]],
            draggable=True,
            icon=folium.DivIcon(html=html),
        ).add_to(m)

    st.caption("Draw shapes. Add labels. Export PNG with the ⤓ button.")
    map_state = st_folium(m, height=560, width=None)

with right:
    st.subheader("Add label")
    label_text = st.text_input("Text", value="POTENTIAL SITE")
    label_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=0)
    label_size = st.slider("Size (px)", 10, 36, 16)
    st.write("Click on the map, then press Add at click.")

    # last click from map
    last = map_state.get("last_clicked") if isinstance(map_state, dict) else None
    st.write(f"Last click: {round(last['lat'],5)},{round(last['lng'],5)}" if last else "Last click: none")

    add = st.button("Add label at last click", type="primary", use_container_width=True)
    if add:
        if not last:
            st.warning("Click the map first.")
        else:
            st.session_state.labels.append(
                {"lat": float(last["lat"]), "lon": float(last["lng"]), "text": label_text, "style": label_style, "size": label_size}
            )
            st.experimental_rerun()

    clear = st.button("Clear all labels", use_container_width=True)
    if clear:
        st.session_state.labels = []
        st.experimental_rerun()
