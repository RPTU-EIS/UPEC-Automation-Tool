"""Frontend for counterexample analysis."""

import io

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src.backend import vcd_analysis as ce
from src.frontend.frontend_utils import bl, tab_header


def format_variable_value(var, value_changes, formatter):
    """Formats the value of a variable using the specified formatter."""
    if var in value_changes:
        return formatter(int(value_changes[var], 2))
    return "unchanged"


def format_vcd_difference(diff_var, value_changes,
                          pairs, var_names, representation, show_prefix):
    """Formats the difference between two paired variables."""
    if representation == "Decimal":
        formatter = str
    elif representation == "Hexadecimal":
        formatter = hex
    else:
        formatter = bin

    paired_var = pairs[diff_var]

    var_name = var_names[diff_var]
    if not show_prefix:
        var_name = var_name[var_name.rfind(".") + 1:]

    value1 = format_variable_value(diff_var, value_changes, formatter)
    value2 = format_variable_value(paired_var, value_changes, formatter)

    return f"{var_name}: {value1} =/= {value2}"


def display_deviations(timestamp, diffs, value_changes,
                       pairs, var_names, representation, show_prefix):
    """Displays deviations for a specific timestamp."""
    st.markdown(
        f"<h5><span style='color: #718DBF'>Deviations at time:</span> {timestamp}</h5>",
        unsafe_allow_html=True
    )
    differences = [
        format_vcd_difference(
            diff,
            value_changes[timestamp],
            pairs,
            var_names,
            representation,
            show_prefix)
        for diff in diffs
    ]
    st.code("\n".join(differences), language=None)


def display_visualization(items, value_changes, pairs, var_names,
                          representation, show_prefix):
    """Displays waveform visualizations for all deviation timestamps."""

    if not items:
        return

    time_intervals = sorted([t for t, _ in items])
    dtick_dynamic = min(np.diff(time_intervals)) if len(
        time_intervals) > 1 else 1

    with st.spinner("Generating figures, please wait..."):
        for idx, (timestamp, diffs) in enumerate(items):
            if not diffs:
                continue

            st.markdown(
                f"<h5><span style='color: #718DBF'>Deviations at time:</span> {timestamp}</h5>",
                unsafe_allow_html=True)

            fig = go.Figure()

            # Highlight the deviation
            # Find the next timestamp with diffs
            next_valid_timestamp = None
            for next_idx in range(idx + 1, len(items)):
                next_ts, next_diffs = items[next_idx]
                if next_diffs:
                    next_valid_timestamp = next_ts
                    break

            # Calculate x1
            if next_valid_timestamp is not None:
                x1 = next_valid_timestamp
            else:
                x1 = max(time_intervals) + dtick_dynamic

            # Highlight deviation time window
            fig.add_vrect(
                x0=timestamp,
                x1=x1,
                fillcolor="rgba(255, 255, 255, 0.2)",
                line_width=1,
                line_color="rgba(255, 255, 255, 0.5)",
                layer="below"
            )

            num_pairs = len(diffs)

            if num_pairs > 2:
                intra_spacing = 4
                inter_pair_spacing = 4
                signal_height = 3
            else:
                intra_spacing = 1
                inter_pair_spacing = 1
                signal_height = 0.8

            for i, diff_var in enumerate(diffs):
                paired_var = pairs[diff_var]
                signal1 = var_names.get(diff_var, diff_var)
                signal2 = var_names.get(paired_var, paired_var)
                signals = [(diff_var, signal1), (paired_var, signal2)]

                for j, (sig_id, display_name) in enumerate(signals):
                    if not show_prefix:
                        display_name = display_name.split(".")[-1]

                    pair_base = i * (2 * intra_spacing + inter_pair_spacing)
                    y_base = pair_base + j * intra_spacing

                    prev_vals = {}
                    rect_start = None
                    rect_value = None

                    # Signal label
                    if j == 0:
                        fig.add_trace(go.Scatter(
                            x=[min(time_intervals) - dtick_dynamic * 0.5],
                            y=[y_base + intra_spacing / 2],
                            text=var_names[diff_var],
                            mode="text",
                            showlegend=False,
                            textfont={"color": 'white', "size": 16},
                            hoverinfo='skip'
                        ))

                    # Walk time
                    for idx2, t in enumerate(time_intervals):
                        val_changes = value_changes.get(t, {})
                        if sig_id in val_changes:
                            prev_vals[sig_id] = val_changes[sig_id]

                        v = prev_vals.get(sig_id, "0")
                        n = int(v, 2)
                        is_last = idx2 == len(time_intervals) - 1

                        if rect_value is None:
                            rect_start = t
                            rect_value = n

                        elif n != rect_value or is_last:
                            x1 = t if n != rect_value else t + dtick_dynamic

                            if rect_value == 0:
                                fig.add_shape(
                                    type="line",
                                    x0=rect_start, x1=x1,
                                    y0=y_base, y1=y_base,
                                    line={"color": 'blue', "width": 1}
                                )
                            else:
                                fig.add_shape(
                                    type="rect",
                                    x0=rect_start, x1=x1,
                                    y0=y_base, y1=y_base + signal_height,
                                    line={"color": 'green', "width": 1},
                                    fillcolor='rgba(0,128,0,0.2)'
                                )

                                text_val = (
                                    str(rect_value) if representation == "Decimal"
                                    else hex(rect_value) if representation == "Hexadecimal"
                                    else bin(rect_value)
                                )

                                fig.add_trace(go.Scatter(
                                    x=[(rect_start + x1) / 2],
                                    y=[y_base + signal_height / 2],
                                    text=[text_val],
                                    mode="text",
                                    showlegend=False,
                                    textfont={"color": 'white', "size": 14},
                                    hoverinfo='skip'
                                ))

                            rect_start = t
                            rect_value = n

                # Separator
                if len(diffs) > 1:
                    separator_y = pair_base + 2 * intra_spacing + inter_pair_spacing / 2
                    fig.add_shape(
                        type="line",
                        x0=min(time_intervals) - dtick_dynamic,
                        x1=max(time_intervals) + dtick_dynamic,
                        y0=separator_y,
                        y1=separator_y,
                        line={"color": 'gray', "width": 1, "dash": 'dot'},
                        layer="above"
                    )

            # Layout
            fig.update_layout(
                xaxis=dict(
                    title="Time",
                    tickmode='linear',
                    dtick=dtick_dynamic,
                    range=[min(time_intervals) - dtick_dynamic,
                           max(time_intervals) + dtick_dynamic],
                    showgrid=True,
                    gridcolor='rgba(211, 211, 211, 0.2)',
                    gridwidth=0.1
                ),
                yaxis={"visible": False, "fixedrange": True},
                height=150 + len(diffs) * 100,
                paper_bgcolor='black',
                plot_bgcolor='black',
                showlegend=False
            )

            st.plotly_chart(fig, width="stretch",
                            key=f"plot_{timestamp}")


def counterexample():
    """Main function for counterexample analysis."""
    tab_header("Customize Analysis")

    # Sidebar controls
    all_diffs = st.sidebar.checkbox("All Signal Differences")
    show_prefix = st.sidebar.checkbox("Complete Submodule Prefix", True)
    representation = st.sidebar.radio(
        bl("Representation"),
        ("Binary", "Decimal", "Hexadecimal"),
        horizontal=True,
        label_visibility="collapsed"
    )

    uploaded_file = st.file_uploader("Verilog Files", "vcd", label_visibility="collapsed")

    if uploaded_file:
        uploaded_file = io.StringIO(uploaded_file.getvalue().decode())

        # Parse and analyze VCD file
        scope, value_changes, _ = ce.parse_vcd_file(uploaded_file)
        instance_1, instance_2 = ce.identify_instances(scope)
        instances  = [instance_1, instance_2]

        if instance_1 == "" or instance_2 == "":
            st.markdown(
                "<h5><span style='color: #FF0000'>No matching submodules found!</span></h5>",
                unsafe_allow_html=True
            )
            return

        pairs, var_names, deviations_by_time, first_deviations_by_time = ce.analyze_cex(
            scope, value_changes, instance_1, instance_2
        )

        if uploaded_file:
            waves_content = generate_waves_file(
            deviations_by_time,
            first_deviations_by_time,
            value_changes,
            var_names,
            instances,
            all_diffs
        )

            st.sidebar.download_button(
                label="Export OneSpin .waves",
                data=waves_content,
                file_name="upec-cex.waves",
                mime="text/plain"
            )

        # Create and style the Tabs
        st.markdown("""
            <style>
            .stTabs [data-baseweb="tab"] {
            width: 50%;
            }
            </style>
            """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Text View", "Visualization"])

        # Text View Tab
        with tab1:
            st.markdown("<br><br>", unsafe_allow_html=True)
            items = deviations_by_time.items() if all_diffs else first_deviations_by_time.items()
            for timestamp, diffs in items:
                if not diffs:
                    continue

                display_deviations(
                    timestamp, diffs, value_changes, pairs, var_names, representation, show_prefix
                )
        # Visualization Tab
        with tab2:
            st.markdown("<br><br>", unsafe_allow_html=True)

            items = list(deviations_by_time.items()
                         if all_diffs else first_deviations_by_time.items())
            display_visualization(
                items, value_changes, pairs, var_names, representation, show_prefix
            )
def generate_waves_file(
    deviations_by_time,
    first_deviations_by_time,
    value_changes,
    var_names,
    instances,
    all_diffs=False
):

    content = [
        "naming_style onespin",
        "# Name Radix Color Is_Clock",
        "rst DEFAULT DEFAULT {false} {false}",
        "clk DEFAULT DEFAULT {true} {false}"
    ]

    items = deviations_by_time.items() if all_diffs else first_deviations_by_time.items()

    for timestamp, diffs in sorted(items):

        if not diffs:
            continue

        content.append(f"SEPARATOR_time_point_{timestamp} NONE DEFAULT {{false}} {{false}}")

        # Decide which variables to show
        if all_diffs:
            vars_to_add = value_changes.get(timestamp, {}).keys()
        else:
            vars_to_add = diffs

        for var_id in vars_to_add:
            display_name = var_names.get(var_id, var_id)

            for instance in instances:
                content.append(
                    f"{instance}/{display_name} DEFAULT DEFAULT {{false}} {{false}}"
                )

    return "\n".join(content)
