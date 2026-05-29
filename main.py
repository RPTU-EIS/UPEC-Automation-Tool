"""The initial start file of streamlit.

This is where streamlit is configured, the options menu is created
and switching between start and menu pages is handled.

The icons for the menu can be found here:
https://icons.getbootstrap.com/
"""

import streamlit as st
from PIL import Image

from src.frontend.plugins.trojan_detection import trojan_detection
from src.frontend.start_page import start_page
from src.frontend.plugins.shortest_path import shortest_path
from src.frontend.plugins.design_overview import design_overview
from src.frontend.plugins.downloads import downloads
from src.frontend.plugins.upec_dit import upec_dit
from src.frontend.plugins.fan_analysis import fan_analysis
from src.frontend.plugins.counterexample import counterexample
from streamlit_option_menu import option_menu

st.set_page_config(page_title="UPEC Tool", page_icon=Image.open(".streamlit/favicon.ico"), layout="wide")

if "project" not in st.session_state or not st.session_state["project"]:
    start_page()
else:
    st.markdown("<style>.element-container:nth-child(2) {margin-top: -60px;}</style>", unsafe_allow_html=True)
    selected = option_menu(
        menu_title=None,
        options=[
            "Design Overview",
            "Fan Analysis",
            "Shortest Path",
            "UPEC-DIT",
            "Trojan Detection",
            "Counterexample",
            "Downloads"
        ],
        icons=[
            "house",
            "diagram-3",
            "signpost",
            "stopwatch",
            "bug",
            "alt",
            "download"
        ],
        orientation="horizontal",
        styles={
            "nav-link": {
                "text-align": "left",
                "--hover-color": "#eee",
            }
        }
    )
    st.markdown("<style>.stTabs {margin-top: -30px;}</style>", unsafe_allow_html=True)
    match selected:
        case "Design Overview":
            design_overview()
        case "Fan Analysis":
            fan_analysis()
        case "Shortest Path":
            shortest_path()
        case "Counterexample":
            counterexample()
        case "Trojan Detection":
            trojan_detection()
        case "UPEC-DIT":
            upec_dit()
        case "Downloads":
            downloads()
