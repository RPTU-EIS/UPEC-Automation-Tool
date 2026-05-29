import os
import tempfile
import zipfile
from io import BytesIO

import streamlit as st

from src.backend.classes.top_module import TopModule
from src.constants import MITER_SUFFIX, OUTPUT
from src.frontend.frontend_utils import load_top_module_manager, bl, tab_header, \
    create_table, create_signal_df
from src.frontend.print_functions import print_equivalence_function, print_equivalence_constraint, print_clocking, \
    print_miter_circuit, print_sv_comment_separator, print_property, print_bind_statement, print_reset_seq, \
    print_tcl_comment_separator
from src.utils import sort_names_by_keywords


def upec_dit():
    """Generates templates and a runnable script for **UPEC-DIT**."""

    tab_header("UPEC-DIT")

    top_module_manager = load_top_module_manager()
    top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
    top_module = top_module_manager.get_top_module_by_name(top_module_name)

    clock = st.sidebar.selectbox(bl("Clock"), top_module.get_clocks())
    reset = st.sidebar.selectbox(bl("Reset"), top_module.get_resets())
    selected_condition = st.sidebar.radio("Condition", ["Active High", "Active Low"], label_visibility="collapsed")
    active_high = selected_condition == "Active High"

    st.write("**UPEC-DIT** is a method for verifying the absence of data-dependent timing channels in hardware designs. It "
             "verifies that the data being processed does not affect the control behavior of the system. To use it, "
             "follow these steps:")
    st.markdown(
        """
        - In the sidebar on the left, verify that the top module, clock, and reset signals are configured correctly.
        - Select all primary ports related to the control behavior, such as handshake signals.
        - The tool will first check for structural connections between the remaining *data* inputs and the selected *control* outputs.
        - If such a connection exists, formal SVA properties can be downloaded and run with a model checker. Simply run the corresponding Tcl script.
        """)
    st.write("For more information about **UPEC-DIT**, please check out our paper:")
    st.link_button(label="Research Paper", url="https://arxiv.org/abs/2308.07757")

    st.write("---")
    ports = top_module.get_primary_ports(True)
    states = top_module.get_states()
    out_ctrl_ports, in_ctrl_ports = control_io_selection(top_module, clock, reset)

    uploaded_files = st.session_state["files"]
    if uploaded_files and len(out_ctrl_ports) > 0:

        in_data_ports = set(top_module.get_primary_inputs()) - {*in_ctrl_ports, clock, reset}
        struct_conn_exists = any(co in top_module.reachable_signals(di, fan_direction=OUTPUT) for di in in_data_ports for co in out_ctrl_ports)

        if not struct_conn_exists:
            st.markdown(f"<h5 style='color: #718DBF;'>Control behavior independent of data inputs!</h5>",
                        unsafe_allow_html=True)
        else:
            with tempfile.TemporaryDirectory() as temp_dir:

                root_dir = os.path.join(temp_dir, f"{top_module_name}-upec-dit")
                rtl_dir = os.path.join(root_dir, "rtl")
                os.makedirs(rtl_dir, exist_ok=True)

                miter_name = top_module_name + MITER_SUFFIX
                miter_filename = miter_name + ".sv"
                miter_filepath = os.path.join(root_dir, miter_filename)

                property_filename = "upec-dit.sv"
                property_filepath = os.path.join(root_dir, property_filename)

                script_filename_onespin = "run-onespin.tcl"
                script_filepath_onespin = os.path.join(root_dir, script_filename_onespin)

                script_filename_jg = "run-jaspergold.tcl"
                script_filepath_jg = os.path.join(root_dir, script_filename_jg)

                # Save uploaded source files to rtl subdirectory
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(rtl_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                with open(miter_filepath, "w") as f:
                    f.write(print_miter_circuit(top_module_name, ports, clock, reset))

                with open(property_filepath, "w") as f:
                    f.write(print_upec_dit_file(clock, reset, active_high, states,
                                                in_ctrl_ports, out_ctrl_ports, miter_name))

                uploaded_file_names = sort_names_by_keywords([file.name for file in uploaded_files], ["pkg", "package"])

                with open(script_filepath_onespin, "w") as f:
                    f.write(print_tcl_script_onespin(uploaded_file_names,
                                                     miter_filename,
                                                     miter_name,
                                                     property_filename))

                with open(script_filepath_jg, "w") as f:
                    f.write(print_tcl_script_jg(uploaded_file_names,
                                                miter_filename,
                                                miter_name,
                                                property_filename,
                                                clock))

                # Create a zip file
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for folder_name, subfolders, filenames in os.walk(temp_dir):
                        for filename in filenames:
                            file_path = os.path.join(folder_name, filename)
                            zip_file.write(file_path, os.path.relpath(file_path, temp_dir))
                zip_buffer.seek(0)

                # Provide download link
                st.download_button(
                    label="Download ZIP",
                    data=zip_buffer,
                    file_name=f"{top_module_name}-upec-dit.zip",
                    mime="application/zip"
                )


def control_io_selection(top_module: TopModule, clock: str, reset: str) -> tuple[list[str], list[str]]:
    """Displays all inputs and outputs and lets the user select which ones are related to control.
       The clock and reset signals (chosen at the sidebar) are ignored.

    Args:
        top_module: Top module instance from which the primary ports are taken
        clock: Name of the clock signal
        reset: Name of the reset signal

    Returns:
        selected_ctrl_outputs: List of control output port names.
        selected_ctrl_inputs: List of control input port names.
    """

    input_signals = top_module.get_primary_inputs(full=True)
    input_signals.pop(clock, None)
    input_signals.pop(reset, None)
    output_signals = top_module.get_primary_outputs(full=True)
    input_data, _ = create_signal_df("Input", input_signals)
    output_data, _ = create_signal_df("Output", output_signals)

    st.markdown(f"<h5 style='color: #718DBF;'>Please select the control ports:</h5>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        grid_in = create_table(input_data, selectable=True)
    with col2:
        grid_out = create_table(output_data, selectable=True)

    selected_ctrl_inputs = [input_data["Input"][i] for i in grid_in.selection.rows]
    selected_ctrl_outputs = [output_data["Output"][i] for i in grid_out.selection.rows]

    return selected_ctrl_outputs, selected_ctrl_inputs


def print_upec_dit_file(clock: str, reset: str, active_high: bool, all_signals: list[str],
                        ctrl_i_signals: list[str], ctrl_o_signals: list[str], miter_name: str,
                        max_latency: int = 10) -> str:
    """Generates the verification IP for UPEC-DIT in SystemVerilog.

    Args:
        clock: Clock signal name
        reset: Reset signal name
        active_high: Reset condition - True if active high
        all_signals: List of all signals in the design
        ctrl_i_signals: List of control inputs
        ctrl_o_signals: List of control outputs
        miter_name: Name of the miter module
        max_latency: Default unrolling of the UPEC-DIT property

    Returns:
        A string that contains the verification IP.
    """
    file_str = f"module property_checker\n  (\n"
    file_str += f"  input {clock}"
    if reset:
        file_str += f",\n  input {reset}"
    file_str += "\n  );\n\n"

    file_str += print_clocking(clock)
    file_str += f"  localparam MAX_LATENCY = {max_latency};\n\n\n"

    # Design might not have any control inputs
    if ctrl_i_signals:
        file_str += print_sv_comment_separator("Control Input Constraint")
        file_str += print_equivalence_constraint("control_input_c", ctrl_i_signals)

    file_str += print_sv_comment_separator("State Equivalence")
    file_str += print_equivalence_function("state_equivalence", all_signals)

    file_str += print_sv_comment_separator("Control Output Equivalence")
    file_str += print_equivalence_function("control_output_equivalence", ctrl_o_signals)

    file_str += print_sv_comment_separator("Reset Sequence")
    file_str += print_reset_seq(reset, active_high)

    file_str += print_sv_comment_separator("UPEC for Data-Independent Timing")
    file_str += print_property("upec_dit_unrolled", "state_equivalence()",
                               "control_output_equivalence() [*MAX_LATENCY]", reset, active_high)

    file_str += "endmodule\n\n"
    file_str += print_bind_statement(miter_name, [clock], reset, active_high)

    return file_str


def print_tcl_script_onespin(filenames: list[str], miter_filename: str, miter_name: str, property_filename: str) -> str:
    """Generates a Tcl setup script for OneSpin that loads the design, the miter, the properties and runs them.

    Args:
        filenames: List that contains the filenames of the uploaded design
        miter_filename: Name of the miter file
        miter_name: Name of the miter module
        property_filename: Name of the property file

    Returns:
        A string that contains the Tcl script.
    """

    file_str = print_tcl_comment_separator("Design Setup and Verification")

    file_str += f"set script_path [file dirname [file normalize [info script]]]\n\n"
    file_str += f"read_verilog -golden -version sv2012 {{\n"
    for filename in filenames:
        file_str += f"  $script_path/rtl/{filename}\n"
    file_str += f"  }}\n\n"
    file_str += f"read_verilog -golden -version sv2012 {{$script_path/{miter_filename}}}\n\n"
    file_str += f"set_elaborate_option -top verilog!work.{miter_name}\n\n"
    file_str += f"elaborate -golden\n\n"
    file_str += f"compile -golden\n\n"
    file_str += f"set_mode mv\n\n"
    file_str += f"read_sva -version {{sv2012}} {{$script_path/{property_filename}}}\n\n"
    file_str += f"check checker_bind.upec_dit_unrolled_p_a\n"
    file_str += f"check -pass checker_bind.upec_dit_unrolled_p_a\n\n"

    return file_str


def print_tcl_script_jg(filenames: list[str], miter_filename: str, miter_name: str, property_filename: str,
                        clock: str) -> str:
    """Generates a Tcl setup script for JasperGold that loads the design, the miter, the properties and runs them.

    Args:
        filenames: List that contains the filenames of the uploaded design
        miter_filename: Name of the miter file
        miter_name: Name of the miter module
        property_filename: Name of the property file
        clock: Name of the clock signal

    Returns:
        A string that contains the Tcl script.
    """

    file_str = f"set script_path [file dirname [file normalize [info script]]]\n\n"
    for filename in filenames:
        file_str += f"analyze -sv12 $script_path/rtl/{filename}\n"
    file_str += f"analyze -sv12  $script_path/{miter_filename}\n"
    file_str += f"analyze -sv12  $script_path/{property_filename}\n"
    file_str += f"elaborate -top {miter_name}\n\n"
    file_str += f"clock {clock}\n\n"
    file_str += f"reset -none\n\n"
    file_str += f"prove -property {miter_name}.checker_bind.upec_dit_unrolled_p_a\n"
    file_str += f"prove -property {miter_name}.checker_bind.upec_dit_unrolled_p_a:precondition1\n\n"

    return file_str
