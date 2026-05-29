import streamlit as st

from src.backend.classes.top_module import TopModule
from src.frontend.frontend_utils import load_top_module_manager, bl, tab_header, create_table, create_signal_df


def design_overview():
    """Displays the **Design Overview** page of the UPEC Tool."""

    tab_header("Design Overview")
    top_module_manager = load_top_module_manager()
    top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
    top_module = top_module_manager.get_top_module_by_name(top_module_name)
    # TODO: Make submodules selectable
    # submodules = [f"Top ({top_module_name})"] + list(top_module.get_submodule_names())
    # submodule_name = st.sidebar.selectbox(bl("Inspect Submodule"), submodules)

    col1, col2 = st.columns([3, 1])
    with col1:
        print_diagnosis(load_top_module_manager().get_diagnostic_data())
    with col2:
        if st.button("Reset Analysis", type="primary", width="stretch"):
            st.session_state.clear()
            st.rerun()

    design_overview_tables(top_module)


def print_diagnosis(diagnostic_data: tuple[int, int, str]):
    """Prints diagnosis information based on build results.

    Args:
        diagnostic_data: A tuple containing the number of errors, number of warnings, and a diagnostic message
    """
    errors = f"{diagnostic_data[0]} Errors" if diagnostic_data[0] != 1 else f"{diagnostic_data[0]} Error"
    warnings = f"{diagnostic_data[1]} Warnings" if diagnostic_data[1] != 1 else f"{diagnostic_data[1]} Warning"
    if diagnostic_data[0] == 0:
        text = bl(fr"Build succeeded ({errors} \& {warnings})")
        if diagnostic_data[2]:
            with st.expander(f":green[{text}]"):
                st.code(diagnostic_data[2])
        else:
            st.write(f":green[{text}]")
    else:
        text = bl(fr"Build failed ({errors} \& {warnings})")
        with st.expander(f":red[{text}]"):
            st.code(diagnostic_data[2])


def design_overview_tables(top: TopModule):
    st.sidebar.write(bl("Detailed View:"))
    show_inputs = st.sidebar.checkbox("Inputs")
    show_outputs = st.sidebar.checkbox("Outputs")
    show_states = st.sidebar.checkbox("State Signals")
    show_nets = st.sidebar.checkbox("Net Signals")

    overview_data = {
        "Category": [],
        "Count": [],
        "Width": []
    }
    categories = [
        ("Input", top.get_primary_inputs(full=True)),
        ("Output", top.get_primary_outputs(full=True)),
        ("Inouts", top.get_primary_inouts(full=True)),
        ("State Signal", top.get_states(full=True)),
        ("Net Signal", top.get_nets(full=True)),
    ]
    data_frames = {}

    for category, signal_dict in categories:
        data_frame, data_width = create_signal_df(category, signal_dict)
        overview_data["Category"].append(category)
        overview_data["Count"].append(len(data_frame[category]))
        overview_data["Width"].append(data_width)
        data_frames[category] = data_frame

    create_table(overview_data)
    if show_inputs:
        create_table(data_frames["Input"])
    if show_outputs:
        create_table(data_frames["Output"])
    if show_states:
        create_table(data_frames["State Signal"])
    if show_nets:
        create_table(data_frames["Net Signal"])
