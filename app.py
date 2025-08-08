# streamlit run app.py
import csv
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, MeasureControl
from branca.element import JavascriptLink, MacroElement
from jinja2 import Template

st.set_page_config(page_title="School Mini-Maps", layout="wide")
DEFAULT_CSV = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

# ------------------------------
# Helpers for color handling
# ------------------------------
def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgba_from_hex(hex_color: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(hex_color or "#FFFFFF")
    a = max(0.0, min(1.0, float(alpha)))
    return f"rgba({r},{g},{b},{a})"

# ------------------------------
# Data
# ------------------------------
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

# ------------------------------
# Hi-res PNG print control
# ------------------------------
class HiResPrint(MacroElement):
    _template = Template("""
    {% macro script(this, kwargs) %}
    (function(){
      var map = {{this._parent.get_name()}};
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

# ------------------------------
# SVG Icon library
# ------------------------------
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

# ------------------------------
# Session state
# ------------------------------
if "labels" not in st.session_state:
    st.session_state.labels = []  # holds text labels and SVG icons
if "last_clicked" not in st.session_state:
    st.session_state.last_clicked = None

# ------------------------------
# UI
# ------------------------------
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
        zoom = st.slider("Zoom", 12, 20, 16)
    with c2:
        base_tiles_url = "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
        labels_tiles_url = "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png"
        attr = "© OpenStreetMap, © CARTO"
    with c3:
        show_school_marker = st.checkbox("Show school marker", value=True)

    draw_color = st.color_picker("Drawing color", "#FF0000")
    draw_weight = st.slider("Drawing line weight", 1, 10, 3)

    def create_folium_map():
        m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None)
        folium.TileLayer(tiles=base_tiles_url, attr=attr, max_zoom=20).add_to(m)
        folium.TileLayer(tiles=labels_tiles_url, attr=attr, max_zoom=20).add_to(m)

        if show_school_marker:
            folium.CircleMarker([lat, lon], radius=6, color="#000", fill=True, fill_opacity=1, tooltip=school).add_to(m)

        Draw(
            export=True,
            filename=f"{school}_drawings.geojson",
            position="topleft",
            draw_options={"polyline": {"shapeOptions": {"color": draw_color, "weight": draw_weight}}},
            edit_options={"edit": True, "remove": True},
        ).add_to(m)

        m.add_child(MeasureControl(primary_length_unit="miles"))

        for lab in st.session_state.labels:
            if lab.get("style") == "SVG_ICON":
                folium.Marker([lab["lat"], lab["lon"]], draggable=True, icon=folium.DivIcon(html=lab["svg"])).add_to(m)
                continue

            style = lab.get("style", "Label")
            size = lab.get("size", 16)
            color = lab.get("color", "#111")

            if style == "Label":
                bg = rgba_from_hex(lab.get("bg_hex", "#FFFFFF"), lab.get("bg_alpha", 0.8))
                html = f"<div style='font-weight:700;font-size:{size}px;color:{color};background:{bg};padding:2px 6px;border:1px solid {color};border-radius:3px'>{lab['text']}</div>"
            elif style == "Outlined":
                bg = rgba_from_hex(lab.get("bg_hex", "#FFFFFF"), lab.get("bg_alpha", 0.8))
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};background:{bg};-webkit-text-stroke:2px #fff;text-shadow:0 0 2px #fff'>{lab['text']}</div>"
            else:
                html = f"<div style='font-weight:800;font-size:{size}px;color:{color};border:2px solid {color};background:{lab.get('fillcolor', '#f6a500')};padding:4px 8px;border-radius:3px'>{lab['text']}</div>"

            folium.Marker([lab["lat"], lab["lon"]], draggable=True, icon=folium.DivIcon(html=html)).add_to(m)

        return m

    m = create_folium_map()
    m.get_root().header.add_child(JavascriptLink("https://unpkg.com/leaflet-easyprint@2.1.9/dist/bundle.min.js"))
    m.add_child(HiResPrint(file_name=school.replace(" ", "_")))
    map_state = st_folium(m, height=560, width=None)

    if map_state.get("last_clicked"):
        st.session_state.last_clicked = map_state["last_clicked"]

with right:
    st.subheader("Add text label")
    new_text = st.text_input("Text", value="New Label")
    new_style = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=1)
    new_size = st.slider("Size (px)", 10, 36, 16)
    if new_style == "Filled (orange)":
        new_fill_color = st.color_picker("Fill color", "#f6a500")
        new_text_color = st.color_picker("Text color", "#111111")
    else:
        new_text_color = st.color_picker("Text color", "#111111")
        new_bg_hex = st.color_picker("Background color", "#FFFFFF")
        new_bg_alpha = st.slider("Background opacity", 0.0, 1.0, 0.8)

    if st.button("Add text at last click"):
        if st.session_state.get("last_clicked"):
            latc = float(st.session_state.last_clicked["lat"])
            lonc = float(st.session_state.last_clicked["lng"])
            item = {
                "lat": latc,
                "lon": lonc,
                "text": new_text,
                "style": new_style,
                "size": new_size,
                "color": new_text_color
            }
            if new_style == "Filled (orange)":
                item["fillcolor"] = new_fill_color
            else:
                item["bg_hex"] = new_bg_hex
                item["bg_alpha"] = float(new_bg_alpha)
            st.session_state.labels.append(item)
            st.experimental_rerun()

    st.divider()

    st.subheader("Add icon")
    icon_name = st.selectbox("Icon", list(ICON_SVGS.keys()))
    icon_size = st.slider("Icon size", 16, 96, 28)
    icon_color = st.color_picker("Icon color", "#111111")
    if st.button("Add icon at last click"):
        if st.session_state.get("last_clicked"):
            latc = float(st.session_state.last_clicked["lat"])
            lonc = float(st.session_state.last_clicked["lng"])
            svg = colorize_svg(ICON_SVGS[icon_name], icon_color)
            html = f"<div style='width:{icon_size}px;height:{icon_size}px'>{svg}</div>"
            st.session_state.labels.append({"lat": latc, "lon": lonc, "style": "SVG_ICON", "size": icon_size, "svg": html})
            st.experimental_rerun()

    st.divider()

    st.subheader("Edit labels/icons")
    if not st.session_state.labels:
        st.info("No labels yet.")
    else:
        idx = st.selectbox("Select", list(range(len(st.session_state.labels))))
        lab = st.session_state.labels[idx]
        if lab.get("style") == "SVG_ICON":
            esize = st.slider("Icon size", 16, 96, lab.get("size", 28))
            ecolor = st.color_picker("Icon color", "#111111")
            if st.button("Apply icon changes"):
                base_svg = None
                for v in ICON_SVGS.values():
                    if v.split(">")[0] in lab["svg"]:
                        base_svg = v
                        break
                base_svg = base_svg or ICON_SVGS["Info"]
                lab["size"] = esize
                lab["svg"] = f"<div style='width:{esize}px;height:{esize}px'>{colorize_svg(base_svg, ecolor)}</div>"
                st.experimental_rerun()
        else:
            etext = st.text_input("Text", value=lab.get("text", ""))
            estyle = st.selectbox("Style", ["Filled (orange)", "Label", "Outlined"], index=["Filled (orange)", "Label", "Outlined"].index(lab.get("style", "Label")))
            esize = st.slider("Size (px)", 10, 36, lab.get("size", 16))
            if estyle == "Filled (orange)":
                efill = st.color_picker("Fill color", lab.get("fillcolor", "#f6a500"))
                ecol = st.color_picker("Text color", lab.get("color", "#111111"))
            else:
                ecol = st.color_picker("Text color", lab.get("color", "#111111"))
                ebg_hex = st.color_picker("Background color", lab.get("bg_hex", "#FFFFFF"))
                ebg_alpha = st.slider("Background opacity", 0.0, 1.0, float(lab.get("bg_alpha", 0.8)))

            if st.button("Apply text changes"):
                lab["text"] = etext
                lab["style"] = estyle
                lab["size"] = esize
                lab["color"] = ecol
                if estyle == "Filled (orange)":
                    lab["fillcolor"] = efill
                    lab.pop("bg_hex", None)
                    lab.pop("bg_alpha", None)
                else:
                    lab["bg_hex"] = ebg_hex
                    lab["bg_alpha"] = float(ebg_alpha)
                    lab.pop("fillcolor", None)
                st.experimental_rerun()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete selected"):
                st.session_state.labels.pop(idx)
                st.experimental_rerun()
        with col2:
            if st.button("Clear all"):
                st.session_state.labels = []
                st.experimental_rerun()
