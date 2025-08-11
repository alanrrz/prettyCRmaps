import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, MeasureControl
from branca.element import JavascriptLink, MacroElement
from jinja2 import Template
import geopy.geocoders

def rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

st.set_page_config(page_title="School Mini-Maps", layout="wide")

# --------------------------------
# Config
# --------------------------------
# Minimalist basemap presets (base + optional labels overlay)
BASEMAPS = {
    "OSM Standard": {
        "base": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "labels": None,
        "attr": "© OpenStreetMap contributors"
    },
    "CARTO Light (no labels)": {
        "base": "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "labels": "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
        "attr": "© OpenStreetMap, © CARTO"
    },
    "CARTO Light (with labels)": {
        "base": "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "labels": "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
        "attr": "© OpenStreetMap, © CARTO"
    },
    "CARTO Dark (no labels)": {
        "base": "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "labels": "https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png",
        "attr": "© OpenStreetMap, © CARTO"
    },
    "CARTO Dark (with labels)": {
        "base": "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "labels": "https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png",
        "attr": "© OpenStreetMap, © CARTO"
    },
    "Stamen Toner (background + labels)": {
        "base": "https://stamen-tiles-{s}.a.ssl.fastly.net/toner-background/{z}/{x}/{y}.png",
        "labels": "https://stamen-tiles-{s}.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}.png",
        "attr": "Map tiles by Stamen Design, CC BY 3.0. Data © OSM."
    },
}

# --------------------------------
# Helpers (color + rgba)
# --------------------------------
def hex_to_rgb(h: str):
    h = (h or "").lstrip("#") or "FFFFFF"
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgba_from_hex(hex_color: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(hex_color or "#FFFFFF")
    a = max(0.0, min(1.0, float(alpha)))
    return f"rgba({r},{g},{b},{a})"

# Hi-res PNG print button
class HiResPrint(MacroElement):
    _template = Template("""
    {% macro script(this, kwargs) %}
    (function(){
      var map = {{this._parent.get_name()}};
      if (!(window.L && L.easyPrint)) {
        console.warn('easyPrint plugin not loaded; export disabled');
        return;
      }
      var originalSize;

      function resizeMap(factor){
        var el = map.getContainer();
        if(!originalSize){
          originalSize = {w: el.clientWidth, h: el.clientHeight};
        }
        el.style.width  = (originalSize.w * factor) + "px";
        el.style.height = (originalSize.h * factor) + "px";
        map.invalidateSize(true);
      }

      var printer = L.easyPrint({
        tileLayer: null,
        sizeModes: ['CurrentSize'],
        filename: '{{this.file_name}}',
        exportOnly: true,
        hideControlContainer: true
      }).addTo(map);

      function toggleControls(show){
        var els = document.querySelectorAll(".leaflet-control, .leaflet-draw, .leaflet-bar");
        els.forEach(function(e){ e.style.display = show ? "" : "none"; });
      }

      var btn = L.control({position: '{{this.position}}'});
      btn.onAdd = function(){
        var div = L.DomUtil.create('div','leaflet-bar');
        var a = L.DomUtil.create('a','',div);
        a.innerHTML = '⤓';
        a.title = 'Export 2x PNG';
        a.href = '#';
        a.style.textAlign = 'center';
        a.style.width = '30px';
        a.style.lineHeight = '30px';
        L.DomEvent.on(a, 'click', function(e){
          L.DomEvent.stop(e);
          toggleControls(false);
          resizeMap(2);
          setTimeout(function(){
            printer.printMap('CurrentSize', '{{this.file_name}}');
            setTimeout(function(){
              var el = map.getContainer();
              el.style.width  = originalSize.w + "px";
              el.style.height = originalSize.h + "px";
              toggleControls(true);
              map.invalidateSize(true);
            }, 500);
          }, 500);
        });
        return div;
      };
      btn.addTo(map);
    })();
    {% endmacro %}
    """)
    def __init__(self, file_name="map_export_2x", position="topleft"):
        super().__init__()
        self._name = "HiResPrint"
        self.file_name = file_name
        self.position = position

# SVG icon set
ICON_SVGS = {
    "Entrance": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><path d='M2 4h18v24H2z'/><path d='M20 16H8l4-4-2-2-8 8 8 8 2-2-4-4h12z'/></svg>",
    "Parking":  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><path d='M6 4h12a8 8 0 010 16H6z'/><rect x='6' y='20' width='6' height='8'/></svg>",
    "Info":     "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='14'/><rect x='15' y='12' width='2' height='12'/><circle cx='16' cy='8' r='2'/></svg>",
    "Caution":  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><path d='M16 4l14 24H2z'/><rect x='15' y='12' width='2' height='8'/><rect x='15' y='22' width='2' height='2'/></svg>",
    "Office":   "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect x='4' y='6' width='24' height='20'/><rect x='8' y='10' width='6' height='6'/><rect x='18' y='10' width='6' height='6'/></svg>",
}

def colorize_svg(svg: str, fill: str) -> str:
    return (svg
            .replace("<path", f"<path fill='{fill}'")
            .replace("<circle", f"<circle fill='{fill}'")
            .replace("<rect", f"<rect fill='{fill}'"))

# --------------------------------
# Session state
# --------------------------------
if "labels" not in st.session_state:
    st.session_state.labels = []
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None
if "selected_label_idx" not in st.session_state:
    st.session_state.selected_label_idx = 0
if "address_coords" not in st.session_state:
    st.session_state.address_coords = (33.9239, -118.2620) # Default location

# --------------------------------
# App layout
# --------------------------------
st.title("School Mini-Maps")

basemap_choice = st.sidebar.selectbox(
    "Basemap preset",
    list(BASEMAPS.keys()),
    index=list(BASEMAPS.keys()).index("CARTO Light (no labels)")
)
show_label_overlay = st.sidebar.toggle(
    "Show labels overlay",
    value=("with labels" in basemap_choice or "OSM" in basemap_choice or "Stamen" in basemap_choice)
)

# Address input for map centering
address_input = st.sidebar.text_input("Enter Address or Name", "Samuel Gompers Middle School")
search_button = st.sidebar.button("Go to Address")

# Geocoding function to get coordinates from address
@st.cache_data(ttl=3600)
def geocode_address(address):
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    try:
        geolocator = geopy.geocoders.Nominatim(user_agent="streamlit_app")
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        st.error(f"Geocoding service error: {e}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None, None

# Update coordinates only when button is pressed
if search_button:
    with st.spinner("Finding location..."):
        lat, lon = geocode_address(address_input)
        if lat is not None and lon is not None:
            st.session_state.address_coords = (lat, lon)
        else:
            st.error("Could not find address. Showing last known location.")
            if "address_coords" not in st.session_state:
                st.session_state.address_coords = (33.9239, -118.2620)

lat, lon = st.session_state.get("address_coords", (33.9239, -118.2620))

left, right = st.columns([2.2, 1])

with left:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        zoom = st.slider("Zoom", 12, 20, 16, key="zoom")
    with c2:
        show_school_marker = st.checkbox("Show school marker", value=True, key="show_marker")
    with c3:
        draw_weight = st.slider("Drawing line weight", 1, 10, 3, key="draw_w")
    with c4:
        draw_color = st.color_picker("Drawing color", "#FF0000", key="draw_color")

    # Tiles
    bm = BASEMAPS[basemap_choice]
    base_tiles_url = bm["base"]
    labels_tiles_url = bm["labels"]
    attr = bm["attr"]

    # Map builder function
    def create_folium_map():
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=False, zoom_control=True)
        folium.TileLayer(tiles=base_tiles_url, attr=attr, max_zoom=20, name="base").add_to(m)
        if labels_tiles_url and show_label_overlay:
            folium.TileLayer(tiles=labels_tiles_url, attr=attr, max_zoom=20, name="labels").add_to(m)

        if show_school_marker:
            folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1, tooltip=address_input).add_to(m)

        Draw(
            export=True,
            filename=f"map_drawings.geojson",
            position="topleft",
            draw_options={
                "polyline": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "rectangle": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "polygon": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "circle": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "circlemarker": {"shapeOptions": {"color": draw_color, "weight": draw_weight}},
                "marker": False
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(m)

        m.add_child(MeasureControl(primary_length_unit="miles"))

        # Robust label rendering
        for idx, lab in enumerate(st.session_state.labels):
            try:
                if lab.get("style") == "SVG_ICON":
                    folium.Marker([lab["lat"], lab["lon"]], draggable=True, icon=folium.DivIcon(html=lab["svg"])).add_to(m)
                else:
                    style = lab.get("style", "Label")
                    size = lab.get("size", 16)
                    color = lab.get("color", "#111")
                    
                    html_style = ""
                    if style == "Label":
                        bg = rgba_from_hex(lab.get("bg_hex", "#FFFFFF"), lab.get("bg_alpha", 0.8))
                        html_style = f"font-weight:700;font-size:{size}px;color:{color};background:{bg};padding:2px 6px;border:1px solid {color};border-radius:3px"
                    elif style == "Outlined":
                        html_style = f"font-weight:800;font-size:{size}px;color:{color};-webkit-text-stroke:2px #fff;text-shadow:0 0 2px #fff"
                    else:
                        html_style = f"font-weight:800;font-size:{size}px;color:{color};border:2px solid {color};background:{lab.get('fillcolor', '#f6a500')};padding:4px 8px;border-radius:3px"

                    html = f"<div style='{html_style}'>{lab['text']}</div>"
                    folium.Marker([lab["lat"], lab["lon"]], draggable=True, icon=folium.DivIcon(html=html)).add_to(m)
            except Exception as e:
                st.warning(f"Error rendering label {idx}: {e}. Skipping...")

        return m

    m = create_folium_map()

    try:
        m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
        m.add_child(HiResPrint(file_name="map_export_2x"))
    except Exception as e:
        st.warning(f"Hi-res print disabled: {e}")

    st.caption("Draw shapes. Click the map to add a new label or icon.")
    map_state = st_folium(m, height=600, width=None, key="map")

    if map_state.get("last_clicked") and map_state["last_clicked"] != st.session_state.last_clicked:
        st.session_state.last_clicked = map_state["last_clicked"]
        latc = float(st.session_state.last_clicked["lat"])
        lonc = float(st.session_state.last_clicked["lng"])
        
        if st.session_state.get("add_mode", "label") == "label":
            st.session_state.labels.append({
                "lat": latc,
                "lon": lonc,
                "text": "New Label",
                "style": "Label",
                "size": 16,
                "color": "#111",
                "bg_hex": "#FFFFFF",
                "bg_alpha": 0.8
            })
        else:
            icon_name = st.session_state.get("icon_to_add", "Info")
            icon_size = st.session_state.get("icon_size_add", 28)
            icon_color = st.session_state.get("icon_color_add", "#111111")
            svg = colorize_svg(ICON_SVGS[icon_name], icon_color)
            html = f"<div style='width:{icon_size}px;height:{icon_size}px'>{svg}</div>"
            st.session_state.labels.append({
                "lat": latc, 
                "lon": lonc, 
                "style": "SVG_ICON", 
                "size": icon_size, 
                "svg": html,
                "base_svg_key": icon_name,
                "color": icon_color
            })
        
        rerun()
    
with right:
    st.subheader("Add new element")
    add_mode = st.radio("What to add on click?", ["Text Label", "Icon"], key="add_mode_select", horizontal=True)
    st.session_state["add_mode"] = "label" if add_mode == "Text Label" else "icon"

    st.info("Click the map to place a new item.")

    if add_mode == "Text Label":
        st.divider()
        new_text = st.text_input("Default Text", value="New Label")
        new_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=1)
        new_size = st.slider("Size (px)", 10, 36, 16)
        if new_style == "Filled (orange)":
            new_fill_color = st.color_picker("Fill color", "#f6a500")
            new_text_color = st.color_picker("Text color", "#111111")
        else:
            new_text_color = st.color_picker("Text color", "#111111")
            new_bg_hex = st.color_picker("Background color", "#FFFFFF")
            new_bg_alpha = st.slider("Background opacity", 0.0, 1.0, 0.8)

    else:
        st.divider()
        icon_name = st.selectbox("Icon", list(ICON_SVGS.keys()), key="icon_to_add")
        icon_size = st.slider("Icon size", 16, 96, 28, key="icon_size_add")
        icon_color = st.color_picker("Icon color", "#111111", key="icon_color_add")
    
    st.divider()
    st.subheader("Edit existing elements")
    if not st.session_state.labels:
        st.info("No labels or icons yet.")
    else:
        label_options = [
            f"{i}: {lab.get('text', lab.get('base_svg_key'))}" for i, lab in enumerate(st.session_state.labels)
        ]
        selected_label_index = st.selectbox("Select an element to edit", range(len(st.session_state.labels)), format_func=lambda x: label_options[x], key="selected_label_idx")

        lab = st.session_state.labels[selected_label_index]
        
        if lab.get("style") == "SVG_ICON":
            new_icon_name = st.selectbox("Icon type", list(ICON_SVGS.keys()), index=list(ICON_SVGS.keys()).index(lab.get("base_svg_key", "Info")), key=f"edit_icon_name_{selected_label_index}")
            new_icon_size = st.slider("Icon size", 16, 96, lab.get("size", 28), key=f"edit_icon_size_{selected_label_index}")
            new_icon_color = st.color_picker("Icon color", lab.get("color", "#111111"), key=f"edit_icon_color_{selected_label_index}")
            
            if st.button("Apply icon changes", use_container_width=True, key=f"apply_icon_{selected_label_index}"):
                svg = colorize_svg(ICON_SVGS[new_icon_name], new_icon_color)
                lab["size"] = new_icon_size
                lab["color"] = new_icon_color
                lab["base_svg_key"] = new_icon_name
                lab["svg"] = f"<div style='width:{new_icon_size}px;height:{new_icon_size}px'>{svg}</div>"
                rerun()
        else:
            new_text = st.text_input("Text", value=lab.get("text", ""), key=f"edit_text_{selected_label_index}")
            new_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=["Filled (orange)", "Label", "Outlined"].index(lab.get("style", "Label")), key=f"edit_style_{selected_label_index}")
            new_size = st.slider("Size (px)", 10, 36, lab.get("size", 16), key=f"edit_size_{selected_label_index}")
            
            if new_style == "Filled (orange)":
                new_fill_color = st.color_picker("Fill color", lab.get("fillcolor", "#f6a500"), key=f"edit_fillcolor_{selected_label_index}")
                new_text_color = st.color_picker("Text color", lab.get("color", "#111111"), key=f"edit_textcolor_{selected_label_index}")
            else:
                new_text_color = st.color_picker("Text color", lab.get("color", "#111111"), key=f"edit_textcolor_{selected_label_index}")
                new_bg_hex = st.color_picker("Background color", lab.get("bg_hex", "#FFFFFF"), key=f"edit_bg_hex_{selected_label_index}")
                new_bg_alpha = st.slider("Background opacity", 0.0, 1.0, float(lab.get("bg_alpha", 0.8)), key=f"edit_bg_alpha_{selected_label_index}")

            if st.button("Apply text changes", use_container_width=True, key=f"apply_text_{selected_label_index}"):
                lab["text"] = new_text
                lab["style"] = new_style
                lab["size"] = new_size
                lab["color"] = new_text_color
                if new_style == "Filled (orange)":
                    lab["fillcolor"] = new_fill_color
                    lab.pop("bg_hex", None)
                    lab.pop("bg_alpha", None)
                else:
                    lab["bg_hex"] = new_bg_hex
                    lab["bg_alpha"] = float(new_bg_alpha)
                    lab.pop("fillcolor", None)
                rerun()

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete Selected Element", use_container_width=True, key=f"delete_button_{selected_label_index}"):
                st.session_state.labels.pop(selected_label_index)
                st.session_state.selected_label_idx = max(0, selected_label_index - 1)
                rerun()
        with col2:
            if st.button("Clear All Elements", use_container_width=True, key="clear_all_button"):
                st.session_state.labels = []
                st.session_state.selected_label_idx = 0
                rerun()
