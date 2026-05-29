import streamlit as st

from src.backend.classes.top_module import TopModule
from src.constants import FANOUT, FANIN
from src.frontend.frontend_utils import load_top_module_manager, display_subgraph, bl, tab_header, line


def fan_analysis():

    """Displays the **Fan Analysis** page of the UPEC Tool."""

    tab_header("Customize Analysis")

    top_module_manager = load_top_module_manager()
    module_list = top_module_manager.get_top_module_names()
    top_module_name = st.sidebar.selectbox(bl("Top Module"), module_list)
    top_module = top_module_manager.get_top_module_by_name(top_module_name)

    source_list = top_module.get_signals()
    source_signal = st.sidebar.selectbox(bl("Source"), source_list)

    fan_direction_input = st.sidebar.radio(bl("Direction"), ("Fan-out", "Fan-in"), horizontal=True,
                                           label_visibility="collapsed")
    fan_direction = FANOUT if fan_direction_input == "Fan-out" else FANIN
    fan_direction_str = "Fan-out" if fan_direction_input == "Fan-out" else "Fan-in"

    line()

    state_only = not (st.sidebar.checkbox("Include All Signals", False, key=13)) ##inverting to reduce refactors
    st.sidebar.caption(
        "When disabled, only state elements (registers / flops) are shown."
    )
    graph = st.sidebar.checkbox("Show Network", False, key=14)

    st.markdown(
        f"<h5><span style='color: #718DBF'>{fan_direction_str}:</span> {source_signal}</h5>",
        unsafe_allow_html=True)

    if graph:
        line()
        cycle_count = st.sidebar.number_input(bl("Select cycle count"), min_value=1, max_value=30, step=1)
        show_fan(top_module, source_signal, cycle_count, fan_direction, state_only)
    else:
        st.code(print_fan(top_module, source_signal, fan_direction, state_only), language=None)


def show_fan(module: TopModule, source: str, cycle: int, fan_direction: bool, only_state: bool):
    """Creates streamlit component, from the subgraph and the resulting pyvis page.

    Args:
        module: Name of the module
        source: Name of the source signal
        cycle: Depth of analysis in cycles
        fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)
        only_state: **True:** Returns only state signals | **False:** Returns all signals
    """
    #fix for duplicate edges for the same node
    edges = set(module.get_fan_subgraph(source, cycle, fan_direction, only_state))
    nodes = [source] + [node for edge in edges for node in edge]
    fan = nodes, edges
    pyvis_page = display_subgraph(module, source, fan)
    st.iframe(pyvis_page.read(), height=650)

# TODO: Make fan_depth a parameter that can be entered
def print_fan(module: TopModule, source: str, fan_direction: bool, only_state: bool, fan_depth: int = 20) -> str:
    """Creates a text representation from the subgraph.

    Args:
        module: Name of the module
        source: Name of the source signal
        fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)
        only_state: **True:** Returns only state signals | **False:** Returns all signals
        fan_depth: Maximum fan depth

    Returns:
        Structured text output of the fan
    """
    result = ""
    pre = set()
    for i in range(1, fan_depth):
        nodes = module.get_fan_nodes(source, i, fan_direction, only_state)
        diff = nodes - pre
        if not diff:
            break
        result += f"{i}: {sorted(diff)}\n"
        pre = nodes
    return result