import streamlit as st

from src.constants import FANOUT
from src.frontend.frontend_utils import load_top_module_manager, display_subgraph, bl, tab_header, line
from src.utils import sort_signals_hierarchically


def shortest_path():
    """Displays the **Shortest Path** page of the UPEC Tool."""

    tab_header("Customize Analysis")

    top_module_manager = load_top_module_manager()
    top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
    top_module = top_module_manager.get_top_module_by_name(top_module_name)

    source_list = top_module.get_signals()
    source_signal = st.sidebar.selectbox(bl("Source"), source_list)

    target_list = sort_signals_hierarchically(list(top_module.reachable_signals(source_signal, FANOUT)))
    target_signal = st.sidebar.selectbox(bl("Target"), target_list)

    line()

    graph = st.sidebar.checkbox("Show Network", False, key=14)

    st.markdown(
        f"<h5><span style='color: #718DBF'>Shortest Path:</span> {source_signal}"
        f" <span style='color: #718DBF'>➜</span> {target_signal}</h5>",
        unsafe_allow_html=True)

    edges = list(top_module.shortest_path(source_signal, target_signal, FANOUT))
    nodes = [source_signal] + list(dict.fromkeys([a for b in edges for a in b]))

    if graph:
        pyvis_page = display_subgraph(top_module, source_signal, (nodes, edges))
        st.iframe(pyvis_page.read(), height=650)
    else:
        shortest_path_str = ""
        # Cut off the first entry or the source signal will be listed twice.
        for i, signal in enumerate(nodes[1:]):
            shortest_path_str += f"{i}: {signal}\n"
        st.code(shortest_path_str, language=None)
