# Minimal, reliable, fast. No geopandas/osmnx/matplotlib.
# Renders PNGs from OSM tiles using 'staticmap' and converts to black/white with Pillow.

import io
import math
import streamlit as st

try:
    import pandas as pd
    from staticmap import StaticMap, CircleMarker
    from PIL import Image, ImageOps, ImageEnhance
except Exception as e:
    st.error(f"Missing deps. Install exact versions from requirements.txt. Error: {e}")
    st.stop()

st.set_page_config(page_title="LAUSD Mini-Maps (PNG)", layout="wide")
RAW_CSV_DEFAULT = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

@st.cache_data(show_spinner=False)
def load_schools(src):
    df = pd.read_csv(src)
    for c in ("school_name","latitude","longitude"):
        if c not in df.columns:
            raise ValueError(f"Missing column: {c}")
    df = df.dropna(subset=["school_name","latitude","longitude"]).copy()
    df["school_name"] = df["school_name"].astype(str)
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    return df

def render_staticmap(lon, lat, width, height, zoom, tile_url):
    m = StaticMap(width, height, url_template=tile_url, delay_seconds=0)  # no retry delays
    m.add_marker(CircleMarker((lon, lat), '#000000', 12))
    image = m.render(zoom=zoom)
    return image

def to_bw(image, invert=False, boost=1.2, threshold=None):
    # Convert to grayscale
    img = ImageOps.grayscale(image)
    # Boost contrast slightly for tiny prints
    if boost and boost != 1.0:
        img = ImageEnhance.Contrast(img).enhance(boost)
    # Optional binary threshold for photocopy-safe output
    if threshold is not None:
        img = img.point(lambda p: 255 if p > threshold else 0)
    # Optional invert for dark background layouts
    if invert:
        img = ImageOps.invert(img)
    return img

st.title("School Mini-Maps (PNG)")

# Data source
src_mode = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
if src_mode == "GitHub CSV":
    csv_url = st.text_input("Raw CSV URL", RAW_CSV_DEFAULT)
    df = load_schools(csv_url)
else:
    up = st.file_uploader("Upload schools.csv", type=["csv"])
    if not up:
        st.stop()
    df = load_schools(up)

left, right = st.columns([2,1])
with left:
    school = st.selectbox("School", df["school_name"].tolist())
    row = df[df["school_name"] == school].iloc[0]
    lat, lon = float(row["latitude"]), float(row["longitude"])

    c1, c2, c3 = st.columns(3)
    with c1:
        zoom = st.slider("Zoom", 12, 19, 16)
    with c2:
        px = st.select_slider("Export size (px)", options=[512, 768, 1024, 1536, 2048], value=1024)
    with c3:
        bw_mode = st.selectbox("B/W mode", ["Grayscale", "High-contrast", "Binarized"])
    invert = st.checkbox("Invert (white roads on black)", value=False)

    # Tile servers. Keep defaults simple and reliable.
    tile_choice = st.selectbox(
        "Tiles",
        [
            "OpenStreetMap Standard",
            "Carto Light (if available)",
        ],
        index=0,
        help="If Carto fails, use OSM."
    )
    tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png" if tile_choice.startswith("OpenStreetMap") \
        else "https://{a}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"

    render = st.button("Render PNG", type="primary")

with right:
    st.write("Guidelines:")
    st.write("- Use 16–18 zoom for campus-level detail.")
    st.write("- Use 1024–1536 px for small flyers.")
    st.write("- Choose Binarized for photocopy-safe black/white.")

if render:
    img = render_staticmap(lon, lat, px, px, zoom, tile_url)

    if bw_mode == "Grayscale":
        out = to_bw(img, invert=invert, boost=1.1, threshold=None)
    elif bw_mode == "High-contrast":
        out = to_bw(img, invert=invert, boost=1.6, threshold=None)
    else:  # Binarized
        out = to_bw(img, invert=invert, boost=1.3, threshold=160)

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    buf.seek(0)

    st.image(out, caption=f"{school} · zoom {zoom}", use_container_width=True)
    st.download_button(
        "Download PNG",
        data=buf,
        file_name=f"{school.replace(' ','_')}_z{zoom}_{px}px_{bw_mode.replace(' ','_')}{'_inv' if invert else ''}.png",
        mime="image/png",
    )
