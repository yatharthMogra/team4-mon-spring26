import json
from pathlib import Path
from typing import Any

import pydeck as pdk
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
BOUNDARY_FILES = {
    "NTA": BASE_DIR / "data" / "processed" / "nyc_nta_phase1.geojson",
    "Mid-Zoom": BASE_DIR / "data" / "processed" / "nyc_nta_zoom_mid.geojson",
    "Block-Zoom": BASE_DIR / "data" / "processed" / "nyc_nta_zoom_block.geojson",
}

NYC_VIEW = pdk.ViewState(latitude=40.7128, longitude=-74.0060, zoom=10, pitch=0)


def score_to_color(score: float | None) -> list[int]:
    if score is None:
        return [148, 163, 184, 180]
    if score <= 3:
        return [220, 38, 38, 180]
    if score <= 6:
        return [234, 179, 8, 180]
    return [22, 163, 74, 180]


def parse_score(raw_score: Any) -> float | None:
    if raw_score is None:
        return None
    try:
        return float(raw_score)
    except (TypeError, ValueError):
        return None


def feature_label(feature: dict[str, Any]) -> str:
    props = feature.get("properties", {})
    return (
        props.get("nta_name")
        or props.get("name")
        or props.get("nta_code")
        or props.get("cell_id")
        or "Unknown area"
    )


@st.cache_data(show_spinner=False)
def load_boundary_geojson(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    for feature in payload.get("features", []):
        props = feature.setdefault("properties", {})
        score = parse_score(props.get("placeholder_score"))
        fill_color = score_to_color(score)
        props["_fill_r"] = fill_color[0]
        props["_fill_g"] = fill_color[1]
        props["_fill_b"] = fill_color[2]
        props["_fill_a"] = fill_color[3]

    return payload


def main() -> None:
    st.set_page_config(page_title="TenantGuard NYC Demo", layout="wide")
    st.title("TenantGuard NYC Livability Demo")
    st.caption("Interactive demo powered by Streamlit and your preprocessed NYC boundary GeoJSON data.")

    selected_level = st.sidebar.selectbox("Boundary detail level", list(BOUNDARY_FILES.keys()), index=0)
    boundary_path = BOUNDARY_FILES[selected_level]

    if not boundary_path.exists():
        st.error(f"Boundary file missing: {boundary_path}")
        st.info("Run your data preparation script first, then rerun this app.")
        return

    payload = load_boundary_geojson(boundary_path)
    features = payload.get("features", [])
    if not features:
        st.warning("No features found in GeoJSON.")
        return

    boroughs = sorted(
        {
            f.get("properties", {}).get("borough")
            for f in features
            if f.get("properties", {}).get("borough")
        }
    )
    selected_borough = st.sidebar.selectbox("Filter borough", ["All"] + boroughs, index=0)

    if selected_borough == "All":
        filtered_features = features
    else:
        filtered_features = [
            feature
            for feature in features
            if feature.get("properties", {}).get("borough") == selected_borough
        ]

    if not filtered_features:
        st.warning("No features match the current filter.")
        return

    names = sorted({feature_label(feature) for feature in filtered_features})
    selected_name = st.selectbox("Select area for details", names, index=0)
    selected_feature = next(
        (feature for feature in filtered_features if feature_label(feature) == selected_name),
        filtered_features[0],
    )
    props = selected_feature.get("properties", {})

    layer = pdk.Layer(
        "GeoJsonLayer",
        data={"type": "FeatureCollection", "features": filtered_features},
        stroked=True,
        filled=True,
        extruded=False,
        get_fill_color=["_fill_r", "_fill_g", "_fill_b", "_fill_a"],
        get_line_color=[100, 116, 139, 170],
        line_width_min_pixels=1,
        pickable=True,
    )

    tooltip = {
        "html": "<b>{nta_name}</b><br/>Borough: {borough}<br/>Livability Score: {placeholder_score}",
        "style": {"backgroundColor": "#0f172a", "color": "white"},
    }

    col_map, col_info = st.columns([3, 2])
    with col_map:
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=NYC_VIEW,
                tooltip=tooltip,
                map_provider="carto",
                map_style="light",
            )
        )

    with col_info:
        st.subheader(selected_name)
        st.write(f"**Borough:** {props.get('borough', 'N/A')}")
        score = parse_score(props.get("placeholder_score"))
        st.write(f"**Livability Score:** {f'{score:.1f} / 10' if score is not None else 'N/A'}")
        summary = props.get("placeholder_summary", "No summary provided.")
        st.write(summary)

        issues = props.get("top_issues", [])
        st.write("**Top Reported Issues**")
        if issues:
            for issue in issues:
                st.write(f"- {issue}")
        else:
            st.write("- No issue list available.")


if __name__ == "__main__":
    main()
