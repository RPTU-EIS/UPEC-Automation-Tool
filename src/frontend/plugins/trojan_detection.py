"""Streamlit plugin for **golden-free Trojan detection** on hardware designs.

This module wires the UPEC-Tool frontend to a generic flow that:
- Builds **combinational cone (CC) layers** from the selected top module using the graph API
  (one set of state/output signals per clock step).
- Generates a **miter** with two instances of the design under test.
- Emits **fanout commitment functions** (`fanouts_ccK`) that equate corresponding signals
  of both instances per CC layer.
- Produces a **property checker module** (`trojan_properties.sv`) with INIT and FANOUT
  SVA properties plus tool-friendly bindings.
- Packages all RTL, SVA and a ready-to-run **OneSpin Tcl script** into a ZIP archive that
  can be downloaded from the UI.
"""
import os
import tempfile
import zipfile
from io import BytesIO

import streamlit as st

from src.backend.classes.top_module import TopModule
from src.constants import MITER_SUFFIX, INST_1, INST_2
from src.frontend.frontend_utils import load_top_module_manager, bl, tab_header
from src.frontend.print_functions import (
    print_equivalence_function,
    print_miter_circuit,
    print_sv_comment_separator,
    print_clocking,
    print_reset_seq,
    print_property,
    print_bind_statement,
)
from src.utils import sort_names_by_keywords


def trojan_detection():
    """
    Streamlit UI for the Trojan Detection tool.

    Lets the user select the top module, clock/reset, and excluded inputs.
    Builds CC layers, previews them, and generates all required output files:
    - top_miter.sv
    - fanout_commitments.sv
    - trojan_properties.sv
    - run_onespin.tcl
    Finally, bundles everything into a downloadable ZIP.
    """

    tab_header("Trojan Detection")

    top_module_manager = load_top_module_manager()
    top_module_name = st.sidebar.selectbox(bl("Top Module"), top_module_manager.get_top_module_names())
    top_module: TopModule = top_module_manager.get_top_module_by_name(top_module_name)
    clock = st.sidebar.selectbox(bl("Clock"), top_module.get_clocks())
    reset = st.sidebar.selectbox(bl("Reset"), top_module.get_resets())
    cond = st.sidebar.radio("Condition", ["Active High", "Active Low"], label_visibility="collapsed")
    active_high = (cond == "Active High")

    st.write("**Trojan Detection (Golden-Free)** is a formal verification method that identifies stealthy hardware Trojans "
             "without requiring a golden (trusted) reference design. It analyzes how information propagates through the design "
             "over time, layer by layer, to detect malicious logic that violates functional equivalence or controllability rules.")
    st.markdown(
        """
        - In the sidebar on the left, verify that the top module, clock, and reset signals are configured correctly.
        - Also select signals to be excluded from the  CC Layers
        """

    )

    st.write("For more information about **Trojan Detection in Non-Interfering Accelerators**, please check out our paper:")
    st.link_button(label="Research Paper", url="https://ieeexplore.ieee.org/abstract/document/10546664")
    # Need existing uploaded RTL from the Start page
    uploaded_files = st.session_state.get("files", [])
    if not uploaded_files:
        st.info("Upload RTL files on the start page to enable generation.")
        return

    # Primary ports/signals
    ports = top_module.get_primary_ports(True)
    inputs_without_exclusion = list(top_module.get_primary_inputs())

    default_exclude = [clock, reset]

    user_excluded = st.sidebar.multiselect(
        """Select signals to exclude from analysis:""",
        options=inputs_without_exclusion,
        default=[sig for sig in inputs_without_exclusion if sig in default_exclude],
        help="Exclude signals that should not be part of the Trojan analysis (e.g., reset, zeroize, or test signals)."
    )

    # Final list of seed inputs after exclusion
    exclude = list(user_excluded)
    inputs = [i for i in inputs_without_exclusion if i not in exclude]

    # Build CC layers structurally (fanouts of inputs, then of CCk, …)
    cc_layers = _build_cc_layers(top_module, inputs)
    with st.expander("Preview CC layers", expanded=False):
        st.markdown("<div style='height: 60px'></div>", unsafe_allow_html=True)  # cancels the -60px
        for idx, layer in enumerate(cc_layers, start=1):
            st.markdown(f"**CC{idx} ({len(layer)} signals)**")
            st.code(", ".join(sorted(layer)) if layer else "∅")

    create_trojan_detection_zip(uploaded_files, top_module_name, ports, clock, reset, cc_layers, inputs_without_exclusion, exclude, active_high)


def _build_cc_layers(
        top_module: TopModule,
        src_signals: list[str]
) -> list[set[str]]:
    """
    Build CC layers starting from a list of seed signals.

    Each layer contains state/output signals reached in one sequential step
    using TopModule.get_fan_nodes(). Stops automatically when no new signals
    can be added.
    Returns a list of sets: [CC1, CC2, ...].
    """

    layers: list[set[str]] = []
    frontier = set(src_signals)
    seen: set[str] = set()

    states = set(top_module.get_states())
    prim_out = set(top_module.get_primary_outputs())

    while True:
        next_layer: set[str] = set()

        for src in frontier:
            reached = top_module.get_fan_nodes(
                source=src,
                depth=1,
                fan_direction=True,
                only_state=True
            )

            # get_fan_nodes returns {src} ∪ state nodes reachable in 1 cycle
            for node in reached:
                if node == src:
                    continue
                if node in states or node in prim_out:
                    next_layer.add(node)

        # remove nodes that have already appeared in a previous layer
        next_layer -= seen

        # stop when no new nodes found → no more CC layers
        if not next_layer:
            break

        layers.append(next_layer)
        seen |= next_layer
        frontier = next_layer  # proceed to next cycle

    return layers


def _print_fanout_commitments(cc_layers: list[set[str]]) -> str:
    """
    Generate fanouts_ccK() functions.

    Each function compares corresponding signals between instance U1 and U2
    for all signals in CC_k. Returned as a single SystemVerilog string.
    Emit EXACTLY this shape:

    function fanouts_cc1();
    fanouts_cc1 =
        top1.foo ==
        top2.foo &&
        top1.bar ==
        top2.bar;
    endfunction
    """
    lines: list[str] = []
    for k, layer in enumerate(cc_layers, start=1):
        sigs = sorted(layer)
        lines.append(f"function fanouts_cc{k}();\n")
        if not sigs:
            lines.append(f"fanouts_cc{k} = 1'b1;\nendfunction\n\n")
            continue

        lines.append(f"fanouts_cc{k} =\n")
        for i, s in enumerate(sigs):
            sep = " &&" if i < len(sigs) - 1 else ";"
            lines.append(f"\t" + INST_1 + f".{s} ==\n")
            lines.append(f"\t" + INST_2 + f".{s}{sep}\n")
        lines.append("endfunction\n\n")
    return "".join(lines)


def _print_trojan_props_file(clock: str,
                             reset: str,
                             active_high: bool,
                             primary_inputs: list[str],
                             cc_layers: list[set[str]],
                             miter_name: str,
                             user_excluded: list[str]) -> str:
    """
    SystemVerilog properties per the paper:
      - include fanout_commitments.sv
      - input_equivalence(): (in_1==in_2)&&...
      - INIT: ##0 input_equivalence()  implies  ##1 fanouts_cc1()
      - FANOUT k: ##0 fanouts_cck()  implies  ##1 fanouts_cck+1()
      - Assertions use @(posedge clock) disable iff(<reset inactive>)
      - Bind to miter
    """
    s = ["module property_checker\n  (\n"]
    extra_signals = [sig for sig in user_excluded if sig not in [clock, reset]]
    if reset is None or reset == "":
        pass
    else:
        s.append(f"  input {reset},\n")
    s.append(f"  input {clock}\n")
    s.append("  );\n\n")
    s.append('`include "fanout_commitments.sv"\n\n')

    # Clocking and reset sequence comments
    s.append(print_sv_comment_separator("Clock / Reset"))
    s.append(print_clocking(clock))
    if reset is None or reset == "":
        pass
    else:
        # Prints 'None' as the reset sequence if there is no reset signal for the IP
        s.append(print_reset_seq(reset, active_high))

    # Build from current primary_inputs (exclude clk/reset just in case)
    pin = [p for p in primary_inputs if p not in {clock, reset}]
    s.append(print_sv_comment_separator("Inputs Equality"))
    if pin:
        conj = " &&\n    ".join(["(" + INST_1 + f".{n} == " + INST_2 + f".{n})" for n in sorted(set(pin))])
        s.append("  function automatic bit input_equivalence();\n")
        s.append("  input_equivalence = (\n    " + conj + "\n  );\n")
        s.append("  endfunction\n\n")
    else:
        s.append("  function automatic bit input_equivalence();\n  input_equivalence = 1'b1;\n  endfunction\n\n")

    extra_disable = ""
    if extra_signals:
        extra_disable = " || " + " || ".join(
            f"{inst}.{sig}"
            for sig in extra_signals
            for inst in (INST_1, INST_2)
        )

    # INIT: needs at least CC1
    if len(cc_layers) >= 1:
        s.append(print_sv_comment_separator("Initial Property"))
        s.append(
            print_property("init_prop", "input_equivalence()", "##1 fanouts_cc1()", reset + extra_disable if reset else extra_disable, active_high))

    s.append(print_sv_comment_separator(f"Fan-Out Properties"))
    # FANOUT k
    for k in range(1, len(cc_layers)):
        s.append(print_property(f"fanout_prop_{k}", f"fanouts_cc{k}()", f"##1 fanouts_cc{k + 1}()", reset + extra_disable if reset else extra_disable,
                                active_high))

    s.append("endmodule\n\n")
    # Bind to the generated miter top (module name from print_miter_circuit)
    s.append(print_bind_statement(miter_name, [clock], reset, active_high))
    return "".join(s)


def _print_tcl_script_onespin(filenames: list[str], miter_name: str) -> str:
    """
    Generate run_onespin.tcl.

    Reads RTL + miter, compiles the design, loads the SVA checker,
    and runs 'check -all'. Returned as a single Tcl script string.
    """
    lines = ["set script_path [file dirname [file normalize [info script]]]\n\n", "read_verilog -golden -version sv2012 {\n"]
    for fn in filenames:
        lines.append(f"  $script_path/rtl/{fn}\n")
    lines.append(f"  $script_path/{miter_name}.sv\n")
    lines.append("}\n\n")
    lines.append("elaborate -golden\n\n")
    lines.append("compile -golden\n\n")
    lines.append("set_mode mv\n\n")
    lines.append("read_sva {$script_path/sva/trojan_properties.sv}\n\n")
    lines.append("set_check_option -approver1_steps 1 -approver2_steps 0 -approver3_steps 0 -approver4_steps 0 -disprover1_steps 0 -disprover3_steps 0 -disprover6_steps 0 -prover1_steps 0 -prover2_steps 0\n\n")
    lines.append("check -all [get_checks]\n")
    return "".join(lines)


def create_trojan_detection_zip(
        uploaded_files,
        top_module_name,
        ports,
        clock,
        reset,
        cc_layers,
        inputs,
        exclude,
        active_high,
):
    """
    Build the full Trojan Detection package in a temp directory.

    Writes RTL, miter, SVA files, Tcl script, and bundles everything
    into a ZIP returned to Streamlit for download.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Workspace directories
        root_dir = os.path.join(temp_dir, f"{top_module_name}-trojan-detection")
        rtl_dir = os.path.join(root_dir, "rtl")
        sva_dir = os.path.join(root_dir, "sva")
        os.makedirs(rtl_dir, exist_ok=True)
        os.makedirs(sva_dir, exist_ok=True)

        # Save uploaded RTL files
        for uf in uploaded_files:
            with open(os.path.join(rtl_dir, uf.name), "wb") as f:
                f.write(uf.getbuffer())

        # Paths
        miter_name = top_module_name + MITER_SUFFIX
        top_miter_path = os.path.join(root_dir, f"{miter_name}.sv")
        fanout_commitments_path = os.path.join(sva_dir, "fanout_commitments.sv")
        trojan_props_path = os.path.join(sva_dir, "trojan_properties.sv")
        tcl_path = os.path.join(root_dir, "run_onespin.tcl")

        # (1) Miter circuit
        with open(top_miter_path, "w", encoding="utf-8") as f:
            f.write(print_miter_circuit(top_module_name, ports, clock, reset))

        # (2) Fanout commitments
        with open(fanout_commitments_path, "w", encoding="utf-8") as f:
            for idx, layer in enumerate(cc_layers, start=1):
                f.write(print_equivalence_function(f"fanouts_cc{idx}", list(layer)))

        # (3) Trojan properties
        with open(trojan_props_path, "w", encoding="utf-8") as f:
            f.write(
                _print_trojan_props_file(
                    clock=clock,
                    reset=reset,
                    active_high=active_high,
                    primary_inputs=inputs,
                    cc_layers=cc_layers,
                    miter_name=miter_name,
                    user_excluded=exclude,
                )
            )

        # (4) Tcl script
        uploaded_names = sort_names_by_keywords(
            [uf.name for uf in uploaded_files], ["pkg", "package"]
        )
        with open(tcl_path, "w", encoding="utf-8") as f:
            f.write(_print_tcl_script_onespin(uploaded_names, miter_name))

        # (5) Create ZIP in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for folder, _, files in os.walk(root_dir):
                for name in files:
                    full = os.path.join(folder, name)
                    rel = os.path.relpath(full, root_dir)
                    z.write(full, rel)
        zip_buffer.seek(0)

        # (6) Streamlit download button
        st.download_button(
            label="Download Trojan Detection Files",
            data=zip_buffer,
            file_name=f"{top_module_name}-trojan-detection.zip",
            mime="application/zip",
        )
        return None
