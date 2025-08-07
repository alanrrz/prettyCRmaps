import io
import streamlit as st

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    from prettymaps import plot as pretty_plot
except Exception as e:
    st.error(
        "Dependencies not installed. Confirm runtime.txt is '3.11' and requirements are pinned. "
        f"Installer error: {e}"
    )
    st.stop()


st.set_page_config(page_title="LAUSD Mini-Maps", layout="wide")

RAW_CSV = "https://raw.githubusercontent.com/alanrrz/la_buffer_app_clean/main/schools.csv"

@st.cache_data(show_spinner=False)
def load_schools(url: str) -> pd.DataFrame:
    df = pd.read_csv(url).dropna(subset=["school_name"])
    for col in ["latitude", "longitude"]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    df["school_name"] = df["school_name"].astype(str)
    df = df.dropna(subset=["latitude", "longitude"])
    return df

st.title("School Mini-Maps (B/W)")

# Source selector
src = st.radio("Data source", ["GitHub CSV", "Upload CSV"], horizontal=True)
if src == "GitHub CSV":
    url = st.text_input("Raw CSV URL", RAW_CSV)
    df = load_schools(url)
else:
    up = st.file_uploader("Upload schools.csv", type=["csv"])
    if not up:
        st.stop()
    df = load_schools(up)

# Controls
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

if render:
    # Grayscale/photocopy-safe palettes
    if style == "Mono Light":
        bg, fg = "#FFFFFF", "#111111"
        bld_face, bld_edge = "#F7F7F7", "#00000000"
        water_face, green_face = "#EDEDED", "#F3F3F3"
    elif style == "Mono Dark":
        bg, fg = "#0E0E0E", "#FAFAFA"
        bld_face, bld_edge = "#1A1A1A", "#00000000"
        water_face, green_face = "#141414", "#121212"
    else:  # Print Tiny
        bg, fg = "#FFFFFF", "#000000"
        bld_face, bld_edge = "#FFFFFF", "#000000"
        water_face, green_face = "#FFFFFF", "#FFFFFF"

    fig, ax = plt.subplots(figsize=(fig_size_in, fig_size_in), dpi=dpi)
    ax.set_facecolor(bg)

    layers = {
        "perimeter": {"circle": False},
        "streets": {
            "width": {
                "motorway": 3 + line_w,
                "primary": 2 + line_w,
                "secondary": 2 + line_w,
                "tertiary": 1 + line_w,
                "residential": 1 + line_w,
                "path": 0.5 + 0.5 * line_w,
            },
            "zorder": 3,
            "default_color": fg,
        },
        "buildings": {
            "facecolor": bld_face,
            "edgecolor": bld_edge,
            "linewidth": 0.3 if bld_edge != "#00000000" else 0,
            "zorder": 2,
        },
        "water": {"facecolor": water_face, "edgecolor": water_face, "zorder": 1},
        "green": {"facecolor": green_face, "edgecolor": green_face, "zorder": 1},
    }

    center = f"{lat},{lon}"
    pretty_plot(center, radius=radius_m, layers=layers, ax=ax, padding=0.04)
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
