"""Frontend module with functions for the user interface using Streamlit."""

from time import sleep
from timeit import default_timer as timer

import streamlit as st

from src.backend.analysis import Analysis
from src.backend.top_module_manager import TopModuleManager
from src.frontend.frontend_utils import save_files, set_default_signal


def start_page():
    """Displays the start page for the UPEC Tool."""
    st.markdown(
        "<h1 style='text-align: center; margin-top: -65px;'>UPEC Automation Tool</h1>",
        unsafe_allow_html=True)
    st.write("")
    st.session_state["files"] = st.file_uploader("Verilog Files", ["v", "sv", "svh"], True, label_visibility="collapsed")
    st.write("")
    if st.session_state["files"]:
        if st.button("Start analysis", type="primary", width="stretch"):
            file_paths = save_files(st.session_state["files"])
            st.session_state["project"] = analyse_data(file_paths)
            set_default_signal()
            st.rerun()


def analyse_data(file_paths: list[str]) -> TopModuleManager:
    """Creates syntax trees, analyzes signal structure, caches and returns TopModuleManager.

    Args:
        file_paths: List of file paths

    Returns:
        Main TopModuleManager object
    """
    with st.spinner("Creating Syntax Trees..."):
        start = timer()
        analysis = Analysis(file_paths)
        end = timer()
        status_message1 = st.success(f"Successfully created Syntax Trees: {round(end - start, 5)} s")
    with st.spinner("Analysing Signal Structure..."):
        start = timer()
        top_module_manager = analysis.project
        end = timer()
        status_message2 = st.success(f"Successfully analysed Signal Structure: {round(end - start, 5)} s")
    sleep(1)
    status_message1.empty()
    status_message2.empty()
    return top_module_manager
