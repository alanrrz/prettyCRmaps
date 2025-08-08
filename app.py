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
    st.session_state.labels = []
if "drawn_items" not in st.session_state:
    st.session_state.drawn_items = []

st.title("School Mini-Maps")

# Data source
src = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
try:
    if src == "GitHub CSV":
        csv_url = st.text_input("Raw CSV URL", DEFAULT_CSV)
        names, name_map = load_schools(csv_url)
    else:
        up = st.file_uploader("Upload schools.csv", type=["csv"])
        if not up:
            st.stop()
        text = up.read().decode("utf-8")
        names, name_map = load_schools("data:text/plain," + text)
except requests.exceptions.RequestException as e:
    st.error(f"Error loading CSV from URL: {e}")
    st.stop()
except ValueError as e:
    st.error(f"Error processing CSV: {e}")
    st.stop()

left, right = st.columns([2.2, 1])

with left:
    school = st.selectbox("Select school", names)
    lat, lon = name_map[school]["lat"], name_map[school]["lon"]

    c1, c2, c3 = st.columns(3)
    with c1:
        zoom = st.slider("Zoom", 12, 19, 16)
    with c2:
        base = st.selectbox("Style", ["Positron (light)", "DarkMatter", "OSM", "Stamen Toner"], index=0)
    with c3:
        show_school_marker = st.checkbox("Show school marker", value=True)

    # Drawing & Label Options
    st.subheader("Drawing & Label Options")
    draw_color = st.color_picker("Drawing Color", "#FF0000")
    draw_weight = st.slider("Drawing Line Weight", 1, 10, 3)

    # tiles
    if base.startswith("Positron"):
        tiles = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap, © CARTO"
    elif base.startswith("DarkMatter"):
        tiles = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap, © CARTO"
    elif base.startswith("Stamen Toner"):
        tiles = "https://stamen-tiles-{s}.a.ssl.fastly.net/toner/{z}/{x}/{y}.png"
        attr = "Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL."
    else:
        tiles = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attr = "© OpenStreetMap contributors"

    # Map initialization function
    def create_folium_map(lat, lon, zoom, tiles, attr, show_marker, school_name, draw_color, draw_weight):
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
        folium.TileLayer(tiles=tiles, attr=attr, max_zoom=20, name="base").add_to(m)

        if show_marker:
            folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1, tooltip=school_name).add_to(m)
        
        # Add a custom draw plugin with all drawing tools enabled and styled
        Draw(
            export=True,
            filename=f"{school_name}_drawings.geojson",
            position="topleft",
            draw_options={
                "polyline": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "rectangle": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "polygon": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "circle": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "circlemarker": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "marker": False,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(m)
        
        m.add_child(MeasureControl(primary_length_unit="miles"))
        
        # Render existing labels from session state
        for lab in st.session_state.labels:
            style = lab["style"]
            size = lab["size"]
            color = lab.get("color", "#111")
            bgcolor = lab.get("bgcolor", "rgba(255,255,255,0.8)")
            
            if style == "Label":
                html = f"<div style='font-weight:700;font-size:{size}px;color:{color};background:{bgcolor};padding:2px 6px;border:1px solid {color};border-radius:3px'>{lab['text']}</div>"
            elif style == "Outlined":
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};-webkit-text-stroke:2px #fff;text-shadow:0 0 2px #fff'>{lab['text']}</div>"
            else: # Filled (orange)
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};border:2px solid {color};background:{lab.get('fillcolor', '#f6a500')};padding:4px 8px;border-radius:3px'>{lab['text']}</div>"
            
            folium.Marker(
                [lab["lat"], lab["lon"]],
                draggable=True,
                icon=folium.DivIcon(html=html),
            ).add_to(m)
        
        return m

    m = create_folium_map(lat, lon, zoom, tiles, attr, show_school_marker, school, draw_color, draw_weight)
    
    # easy print (PNG)
    m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
    m.add_child(EasyPrint(file_name=school.replace(" ", "_")))
    
    st.caption("Draw shapes. Add labels. Export PNG with the ⤓ button.")
    map_state = st_folium(m, height=560, width=None)

    # Update session state with drawn features
    if map_state.get("all_drawn_features"):
        st.session_state.drawn_items = map_state["all_drawn_features"]

with right:
    st.subheader("Add label")
    label_text = st.text_input("Text", value="POTENTIAL SITE")
    label_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=0)
    label_size = st.slider("Size (px)", 10, 36, 16)
    
    if label_style == "Filled (orange)":
        label_fill_color = st.color_picker("Fill Color", "#f6a500")
        label_text_color = st.color_picker("Text Color", "#112")
    else:
        label_text_color = st.color_picker("Text Color", "#111111")
        label_bg_color = st.color_picker("Background Color", "rgba(255,255,255,0.8)")
    
    st.write("Click on the map, then press Add at click.")
    
    last = map_state.get("last_clicked") if isinstance(map_state, dict) else None
    st.write(f"Last click: {round(last['lat'],5)},{round(last['lng'],5)}" if last else "Last click: none")
    
    add = st.button("Add label at last click", type="primary", use_container_width=True)
    if add:
        if not last:
            st.warning("Click the map first.")
        else:
            label_data = {
                "lat": float(last["lat"]),
                "lon": float(last["lng"]),
                "text": label_text,
                "style": label_style,
                "size": label_size
            }
            if label_style == "Filled (orange)":
                label_data["color"] = label_text_color
                label_data["fillcolor"] = label_fill_color
            else:
                label_data["color"] = label_text_color
                label_data["bgcolor"] = label_bg_color
            
            st.session_state.labels.append(label_data)
            st.experimental_rerun()
            
    st.subheader("Modify Labels")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Undo Last Label", use_container_width=True):
            if st.session_state.labels:
                st.session_state.labels.pop()
                st.experimental_rerun()
    with col2:
        if st.button("Clear all labels", use_container_width=True):
            st.session_state.labels = []
            st.experimental_rerun()
