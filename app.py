# School Mini-Maps (B/W) — Streamlit + prettymaps
# Loads your GitHub CSV by default, renders ultra-minimal static maps, exports PNGs.

import io
import sys
import traceback
import streamlit as st

# Fail-safe imports with a clear error if deps are missing
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    from prettymaps import plot as pretty_plot
except Exception as e:
    st.error(
        "Dependencies not installed. Confirm runtime.txt is '3.11' and requirements.txt pins "
        "versions as provided. Installer error:\n\n"
        f"{e}\n\n"
        f"{traceback.format_exc()}"
    )
    st.stop()

st.set_page_config(page_title="LAUSD Mini-Maps", layout="wide")

RAW_CSV_DEFAULT = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

@st.cache_data(show_spinner=False)
def load_schools_csv(src):
    if hasattr(src, "read"):
        df = pd.read_csv(src)
    else:
        df = pd.read_csv(src)
    if "school_name" not in df.columns:
        raise ValueError("Missing required column: school_name")
    if "latitude" not in df.columns or "longitude" not in df.columns:
        raise ValueError("Missing required columns: latitude, longitude")
    df = df.dropna(subset=["school_name", "latitude", "longitude"]).copy()
    df["school_name"] = df["school_name"].astype(str)
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    return df

def get_style_palette(style: str, line_w: int):
    if style == "Mono Light":
        return dict(
            bg="#FFFFFF", fg="#111111",
            bld_face="#F7F7F7", bld_edge="#00000000",
            water_face="#EDEDED", green_face="#F3F3F3",
            lw=line_w
        )
    if style == "Mono Dark":
        return dict(
            bg="#0E0E0E", fg="#FAFAFA",
            bld_face="#1A1A1A", bld_edge="#00000000",
            water_face="#141414", green_face="#121212",
            lw=line_w
        )
    # Print Tiny
    return dict(
        bg="#FFFFFF", fg="#000000",
        bld_face="#FFFFFF", bld_edge="#000000",
        water_face="#FFFFFF", green_face="#FFFFFF",
        lw=line_w
    )

def make_layers(pal):
    lw = pal["lw"]
    return {
        "perimeter": {"circle": False},
        "streets": {
            "width": {
                "motorway": 3 + lw,
                "primary": 2 + lw,
                "secondary": 2 + lw,
                "tertiary": 1 + lw,
                "residential": 1 + lw,
                "path": 0.5 + 0.5 * lw,
            },
            "zorder": 3,
            "default_color": pal["fg"],
        },
        "buildings": {
            "facecolor": pal["bld_face"],
            "edgecolor": pal["bld_edge"],
            "linewidth": 0.3 if pal["bld_edge"] != "#00000000" else 0,
            "zorder": 2,
        },
        "water": {"facecolor": pal["water_face"], "edgecolor": pal["water_face"], "zorder": 1},
        "green": {"facecolor": pal["green_face"], "edgecolor": pal["green_face"], "zorder": 1},
    }

st.title("School Mini-Maps (B/W)")

# Data source controls
src_choice = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
if src_choice == "GitHub CSV":
    csv_url = st.text_input("Raw CSV URL", RAW_CSV_DEFAULT)
    try:
        df = load_schools_csv(csv_url)
    except Exception as e:
        st.error(f"CSV load failed: {e}")
        st.stop()
else:
    up = st.file_uploader("Upload schools.csv", type=["csv"])
    if not up:
        st.stop()
    try:
        df = load_schools_csv(up)
    except Exception as e:
        st.error(f"CSV load failed: {e}")
        st.stop()

left, right = st.columns([2, 1])

with left:
    school = st.selectbox("School", options=df["school_name"].tolist())
    row = df[df["school_name"] == school].iloc[0]
    lat, lon = float(row["latitude"]), float(row["longitude"])

    c1, c2, c3 = st.columns(3)
    with c1:
        radius_m = st.slider("Radius (m)", 200, 2500, 900, step=50)
    with c2:
        line_w = st.slider("Line weight", 0, 4, 1, step=1)
    with c3:
        dpi = st.selectbox("Export DPI", [150, 300, 450, 600], index=3)

    style = st.selectbox("Style", ["Print Tiny", "Mono Light", "Mono Dark"], index=0)
    fig_size_in = st.slider("Figure size (inches)", 3.0, 10.0, 5.0, 0.5)

render = st.button("Render", type="primary")

with right:
    st.subheader("Notes")
    st.write("- Use small radii for clarity in tiny prints.")
    st.write("- ‘Print Tiny’ is pure outlines for photocopies.")
    st.write("- Export at 450–600 DPI for small callouts.")

if render:
    pal = get_style_palette(style, line_w)
    layers = make_layers(pal)

    fig, ax = plt.subplots(figsize=(fig_size_in, fig_size_in), dpi=dpi)
    ax.set_facecolor(pal["bg"])

    center = f"{lat},{lon}"
    try:
        pretty_plot(center, radius=radius_m, layers=layers, ax=ax, padding=0.04)
    except Exception as e:
        st.error(
            "Map render failed. OSM network or geospatial deps may be missing. "
            f"Error: {e}"
        )
        st.stop()

    ax.set_axis_off()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0)
    buf.seek(0)

    st.pyplot(fig, use_container_width=True)
    st.download_button(
        "Download PNG",
        data=buf,
        file_name=f"{school.replace(' ', '_')}_{radius_m}m_{style.replace(' ','_')}.png",
        mime="image/png",
    )

