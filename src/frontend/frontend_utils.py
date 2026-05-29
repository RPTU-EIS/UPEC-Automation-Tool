"""Utility module with functions for the frontend."""
from pathlib import Path

import pandas as pd
import streamlit as st
from pyvis.network import Network

from src.backend.classes.subclasses import Signal
from src.backend.classes.top_module import TopModule
from src.backend.top_module_manager import TopModuleManager


def bl(text: str) -> str:
    """Creates a bold LaTeX element which can be displayed in streamlit.

    Examples:
        >>> bl("Build succeeded")
        "$\\sf Build\\ succeeded$"
    """
    text = text.replace(" ", r"\ ")
    return f"$\\sf {text}$"


def tab_header(text: str):
    """Displays a styled header for a Streamlit sidebar tab.

    Args:
        text: The text to be displayed in the header
    """
    st.sidebar.markdown(
        f"<h1 style='text-align: center; color: #718DBF; margin-top: -75px;'>{text}</h1>"
        f"<hr style='margin-top: -10px; margin-bottom: 75px;border-width: 2px; background-color: #718DBF;'>",
        unsafe_allow_html=True)


def line():
    """Displays a horizontal line in a Streamlit sidebar."""
    st.sidebar.markdown("<hr style='margin-top: 0px; margin-bottom: 15px;border-width: 1px;'>", unsafe_allow_html=True)


def save_files(files: list) -> list[str]:
    """Saves streamlit uploads to the cache directory and returns paths.

    Args:
        files: List of uploaded files to be saved

    Returns:
        List of file paths where the files are saved
    """

    cache_dir = Path("cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    file_paths = []
    for file in files:
        file_path = cache_dir / file.name
        file_paths.append(str(file_path))

        with open(file_path, "wb") as f:
            f.write(file.getbuffer())

    return file_paths


def set_default_signal():
    """Sets default values for Streamlits session_state variables."""
    top_module_manager = load_top_module_manager()
    if "top_module" not in st.session_state or not st.session_state["top_module"]:
        st.session_state["top_module"] = top_module_manager.get_top_module_names()[0]
    if "instance" not in st.session_state:
        st.session_state["instance"] = ""
    if "signal" not in st.session_state or not st.session_state["signal"]:
        top_module_name = st.session_state["top_module"]
        st.session_state["signal"] = list(top_module_manager.get_top_module_by_name(top_module_name).get_signals())[0]


def load_state_data() -> tuple[TopModuleManager, TopModule, str, str]:
    """Loads and returns relevant data from Streamlits session_state.

    Returns:
        A tuple containing project, top_module, instance, and signal
    """
    data = st.session_state
    return data["project"], data["top_module"], data["instance"], data["signal"]


def load_top_module_manager() -> TopModuleManager:
    """Loads main TopModuleManager instance containing all structural information.

    Returns:
        TopModuleManager instance"""
    return st.session_state["project"]


def load_top_module_name() -> str:
    """Loads the name of the currently selected top module.

    Returns:
        Top module name instance"""
    return st.session_state["top_module"]


def create_table(data: dict[str, list], selectable: bool = False):
    df = pd.DataFrame(data)
    event = st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        on_select="rerun" if selectable else "ignore",
    )
    return event


def display_subgraph(module: TopModule, source: str, sub_graph: tuple[list[str], list[tuple[str, str]]]):
    """Creates a pyvis page which can then be opened and used by streamlit.

    Args:
        module: TopModule instance to which the subgraph belongs
        source: Name of the source signal
        sub_graph: Subgraph to be displayed
    """
    nt = Network(height="650px", directed=True, bgcolor="#1A1C24", font_color="#D4D4D4")
    nodes, edges = sub_graph
    size = 10
    edge = "#648fc9"
    state = "#97c2fc"
    net = "#c47474"
    nt.add_node(source, size=20, color=state)
    for n in list(nodes)[1:]:
        if module.is_state(n):
            if module.is_port(n):
                nt.add_node(n, size=size, shape="diamond", color=state)
            else:
                nt.add_node(n, size=size, color=state)
        else:
            if module.is_port(n):
                nt.add_node(n, size=size, shape="diamond", color=net)
            else:
                nt.add_node(n, size=size, color=net)
    for e in edges:
        nt.add_edge(e[0], e[1], color=edge)
    nt.set_template(".streamlit/template.html")
    nt.write_html("cache/pyvis_graph.html")
    return open("cache/pyvis_graph.html")


def create_signal_df(header: str, signals: dict[str, Signal]) -> tuple[dict[str, list], int]:
    """
    Creates a data frame for name and width from a dict of signals.
    Used to be displayed in tables.
    :param header: Category of the signals (e.g. "Inputs"), will be in the header of the table.
    :param signals: Signal dict (signal name -> signal object).
    :return: Data frame dictionary and cumulative width of all signals.
    """
    data_frame = {
        header: [],
        "Width": []
    }
    cumulative_width = 0
    for s_name, s_obj in signals.items():
        data_frame[header].append(s_name)
        data_frame["Width"].append(s_obj.width)
        cumulative_width += s_obj.width
    return data_frame, cumulative_width
