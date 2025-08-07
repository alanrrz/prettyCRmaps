import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw

st.set_page_config(layout="wide")
st.title("LAUSD Site Planning Map")
st.caption("Draw proposed sites, boundaries, and markers directly on the map.")

# Centered on Gompers MS
m = folium.Map(
    location=[33.928, -118.273],  # Near 11300 S Main St, Los Angeles
    zoom_start=18,
    tiles="CartoDB positron"
)

# Add drawing tools
draw = Draw(
    export=True,
    filename='drawn_features.geojson',
    position='topleft',
    draw_options={
        'polyline': False,
        'polygon': True,
        'circle': False,
        'rectangle': True,
        'marker': True,
        'circlemarker': False
    },
    edit_options={'edit': True}
)
draw.add_to(m)

# Render the interactive map
output = st_folium(m, width=1000, height=700)

# Show GeoJSON of drawn features
if output.get("all_drawings"):
    st.subheader("Drawn GeoJSON Data")
    st.json(output["all_drawings"])
