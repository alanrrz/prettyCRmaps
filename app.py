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
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

st.title("School Mini-Maps")

try:
    names, name_map = load_schools(DEFAULT_CSV)
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

    st.subheader("Drawing & Label Options")
    draw_color = st.color_picker("Drawing Color", "#FF0000")
    draw_weight = st.slider("Drawing Line Weight", 1, 10, 3)

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

    def create_folium_map(lat, lon, zoom, tiles, attr, show_marker, school_name, draw_color, draw_weight):
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
        folium.TileLayer(tiles=tiles, attr=attr, max_zoom=20, name="base").add_to(m)

        if show_marker:
            folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1, tooltip=school_name).add_to(m)
        
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
        
        for lab in st.session_state.labels:
            style = lab["style"]
            size = lab["size"]
            color = lab.get("color", "#111")
            bgcolor = lab.get("bgcolor", "rgba(255,255,255,0.8)")
            
            if style == "Label":
                html = f"<div style='font-weight:700;font-size:{size}px;color:{color};background:{bgcolor};padding:2px 6px;border:1px solid {color};border-radius:3px'>{lab['text']}</div>"
            elif style == "Outlined":
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};-webkit-text-stroke:2px #fff;text-shadow:0 0 2px #fff'>{lab['text']}</div>"
            else:
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};border:2px solid {color};background:{lab.get('fillcolor', '#f6a500')};padding:4px 8px;border-radius:3px'>{lab['text']}</div>"
            
            folium.Marker(
                [lab["lat"], lab["lon"]],
                draggable=True,
                icon=folium.DivIcon(html=html),
            ).add_to(m)
        
        return m

    m = create_folium_map(lat, lon, zoom, tiles, attr, show_school_marker, school, draw_color, draw_weight)
    
    m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
    m.add_child(EasyPrint(file_name=school.replace(" ", "_")))
    
    st.caption("Draw shapes. Click the map to add a new label.")
    map_state = st_folium(m, height=560, width=None)

    if map_state.get("last_clicked"):
        st.session_state.last_clicked = map_state["last_clicked"]
        if st.session_state.last_clicked:
            new_label_lat = st.session_state.last_clicked['lat']
            new_label_lon = st.session_state.last_clicked['lng']
            st.session_state.labels.append({
                "lat": float(new_label_lat),
                "lon": float(new_label_lon),
                "text": "New Label",
                "style": "Label",
                "size": 16,
                "color": "#111",
                "bgcolor": "rgba(255,255,255,0.8)"
            })
            st.session_state.last_clicked = None
            st.experimental_rerun()
    
with right:
    st.subheader("Edit Labels")
    if not st.session_state.labels:
        st.info("Click on the map to add your first label.")
    else:
        label_options = [f"{i}: {lab['text']}" for i, lab in enumerate(st.session_state.labels)]
        selected_label_index = st.selectbox("Select a label to edit", list(range(len(st.session_state.labels))), format_func=lambda x: label_options[x])

        label_to_edit = st.session_state.labels[selected_label_index]
        
        new_text = st.text_input("Text", value=label_to_edit["text"], key=f"text_{selected_label_index}")
        new_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=["Filled (orange)", "Label", "Outlined"].index(label_to_edit.get("style", "Label")), key=f"style_{selected_label_index}")
        new_size = st.slider("Size (px)", 10, 36, value=label_to_edit.get("size", 16), key=f"size_{selected_label_index}")
        
        if new_style == "Filled (orange)":
            new_fill_color = st.color_picker("Fill Color", value=label_to_edit.get("fillcolor", "#f6a500"), key=f"fillcolor_{selected_label_index}")
            new_text_color = st.color_picker("Text Color", value=label_to_edit.get("color", "#112"), key=f"textcolor_{selected_label_index}")
        else:
            new_text_color = st.color_picker("Text Color", value=label_to_edit.get("color", "#111111"), key=f"textcolor_{selected_label_index}")
            new_bg_color = st.color_picker("Background Color", value=label_to_edit.get("bgcolor", "rgba(255,255,255,0.8)"), key=f"bgcolor_{selected_label_index}")

        if st.button("Apply Changes", use_container_width=True, key=f"update_button_{selected_label_index}"):
            st.session_state.labels[selected_label_index]["text"] = new_text
            st.session_state.labels[selected_label_index]["style"] = new_style
            st.session_state.labels[selected_label_index]["size"] = new_size
            st.session_state.labels[selected_label_index]["color"] = new_text_color
            if new_style == "Filled (orange)":
                st.session_state.labels[selected_label_index]["fillcolor"] = new_fill_color
                st.session_state.labels[selected_label_index].pop("bgcolor", None)
            else:
                st.session_state.labels[selected_label_index]["bgcolor"] = new_bg_color
                st.session_state.labels[selected_label_index].pop("fillcolor", None)
            st.experimental_rerun()

        st.subheader("Manage Labels")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete Selected Label", use_container_width=True, key=f"delete_button_{selected_label_index}"):
                st.session_state.labels.pop(selected_label_index)
                st.experimental_rerun()
        with col2:
            if st.button("Clear All Labels", use_container_width=True, key="clear_all_button"):
                st.session_state.labels = []
                st.experimental_rerun()
