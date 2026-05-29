import json

import streamlit as st

from src.backend.classes.top_module import TopModule
from src.constants import FANOUT, FANIN, MITER_SUFFIX
from src.frontend.frontend_utils import load_top_module_manager, bl, tab_header, line
from src.frontend.print_functions import print_equivalence_function, print_miter_circuit


def downloads():
    """Displays the **Downloads** page of the UPEC Tool."""

    top_module_manager = load_top_module_manager()

    tab_header("Select scheme")
    download = st.sidebar.selectbox("Select scheme",
                                    ("Export Fan-In/Fan-Out (JSON)",
                                     "Miter Circuit",
                                     "State Equivalence"),
                                    label_visibility="collapsed")
    line()
    match download:

        case "Export Fan-In/Fan-Out (JSON)":
            top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
            top_module = top_module_manager.get_top_module_by_name(top_module_name)
            line()
            fan_direction = st.sidebar.radio("Fan-Direction", ("Fan-out", "Fan-in"), horizontal=True, key=21,
                                             label_visibility="collapsed")
            if fan_direction == "Fan-out":
                st.sidebar.download_button(
                    label="Download",
                    data=create_fan_json(top_module, FANOUT),
                    file_name="fanout.json")
            else:
                st.sidebar.download_button(
                    label="Download",
                    data=create_fan_json(top_module, FANIN),
                    file_name="fanin.json")

        case "Miter Circuit":
            top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
            top_module = top_module_manager.get_top_module_by_name(top_module_name)
            ports = top_module.get_all_ports(True)
            clock = st.sidebar.selectbox(bl("Clock"), top_module.get_clocks())
            reset = st.sidebar.selectbox(bl("Reset"), top_module.get_resets())
            st.sidebar.download_button(
                label="Download",
                data=print_miter_circuit(top_module_name, ports, clock, reset),
                file_name=top_module_name + MITER_SUFFIX + ".sv")

        case "State Equivalence":
            top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
            top_module = top_module_manager.get_top_module_by_name(top_module_name)
            states = top_module.get_states()
            data = print_equivalence_function("state_equivalence", states)
            st.sidebar.download_button(
                label="Download",
                data=data,
                file_name="state_equivalence.sva")


def create_fan_json(top_module: TopModule, fan_direction: bool) -> str:
    """Creates a JSON representation of the fan-in/fan-out of all state signals in the given module.

    Args:
        top_module: TopModule instance containing information about states and fans
        fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)

    Returns:
        A JSON string representing signals and their corresponding fans
    """
    result = dict()
    for signal in top_module.get_states():
        result[signal] = list(top_module.get_fan_nodes(signal, 1, fan_direction, True))
    return json.dumps(result, indent=4)
