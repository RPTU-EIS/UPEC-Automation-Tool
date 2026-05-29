"""General printing functions that may be useful for multiple plugins."""

import warnings

from src.constants import INST_1, INST_2, MITER_SUFFIX


def print_equivalence_expression(signals: list[str], indent: int = 4) -> str:
    """Generates a SystemVerilog expression that requires all given signals to be equal between the two instances.

    Args:
        signals: List of signal names
        indent: Number of spaces to indent the string

    Returns:
        A string that contains the expression.
        This function will have a default indent of four.
    """

    if not signals:
        warnings.warn("Warning: Empty equivalence expression generated.")
        return ""

    max_name_len = max(len(ctrl_signal) for ctrl_signal in signals)
    return " &&\n".join(
        f"{' ' * indent}({INST_1}.{signal:<{max_name_len}} == {INST_2}.{signal:<{max_name_len}})" for signal in signals)


def print_equivalence_function(function_name: str, signals: list[str], indent: int = 2) -> str:
    """Generates a SystemVerilog function that requires all given signals to be equal between the two instances.

    Args:
        function_name: Name of the function
        signals: List of signal names
        indent: Number of spaces to indent the string

    Returns:
        A string that contains the function.
        This function will have a default indent of two.
    """

    func_str = ""

    if not signals:
        warnings.warn("Warning: Empty equivalence function generated.")
        return func_str

    func_str += f"{' ' * indent}function automatic {function_name}();\n"
    func_str += f"{' ' * indent}{function_name} = (\n"
    func_str += print_equivalence_expression(signals, indent + 2)
    func_str += f"\n{' ' * indent});\n"
    func_str += f"{' ' * indent}endfunction\n\n\n"

    return func_str


def print_equivalence_constraint(constraint_name: str, signals: list[str]) -> str:
    """Generates a SystemVerilog property that constraints all given signals to be equal between the two instances.

    Args:
        constraint_name: Name of the constraint
        signals: List of signal names

    Returns:
        A string that contains the constraint.
        This constraint will have an indent of two.
    """

    constraint_str = ""

    if not signals:
        warnings.warn("Warning: Empty equivalence constraint generated.")
        return constraint_str

    constraint_str += f"  property {constraint_name};\n"
    constraint_str += print_equivalence_expression(signals)
    constraint_str += ";\n  endproperty\n"
    constraint_str += f"  {constraint_name}_a: assume property ({constraint_name});\n\n\n"

    return constraint_str


def print_clocking(clock: str) -> str:
    return f"  default clocking default_clk @(posedge {clock}); endclocking\n\n"


def print_reset_seq(reset: str, active_high: bool = True) -> str:
    reset_val = "1'b1" if active_high else "1'b0"
    return f"  sequence reset_sequence;\n    ({reset} == {reset_val});\n  endsequence\n\n\n"


def print_miter_circuit(module_name: str, ports: dict, clock: str, reset: str) -> str:
    """Generates a miter circuit of the given module in SystemVerilog.

    Args:
        module_name: Name of the miter module to be instantiated twice in the miter circuit
        ports: Dictionary of port objects with attributes (range, width, direction)
        clock: Name of the clock signal
        reset: Name of the reset signal (None if not existent)

    Returns:
        A string that represents the miter in SystemVerilog.
    """
    width_indent = max(len(port_obj.type_str) for port_obj in ports.values())
    name_indent = max(len(port_name + port_obj.unpacked_suffix) for port_name, port_obj in ports.items()) + 1

    miter_str = "`default_nettype wire\n\n"
    miter_str += f"module {module_name}{MITER_SUFFIX} (\n"
    miter_str += f"  input  {'logic':<{width_indent}} {clock},\n"
    if reset:
        miter_str += f"  input  {'logic':<{width_indent}} {reset},\n"

    for port_name, port_obj in ports.items():
        if port_name in (clock, reset):
            continue
        miter_str += "  output " if port_obj.direction else "  input  "
        miter_str += f"{port_obj.type_str:<{width_indent}} "
        miter_str += f"{port_name + '_1' + port_obj.unpacked_suffix + ',':<{name_indent + 2}} "
        miter_str += f"{port_name}_2{port_obj.unpacked_suffix},\n"
    miter_str = miter_str[:-2] + "\n);\n\n"

    for i, instance in enumerate((INST_1, INST_2)):
        miter_str += f"  {module_name} {instance} (\n"
        miter_str += f"    .{clock:<{name_indent}}({clock:<{name_indent + 1}}),\n"
        if reset:
            miter_str += f"    .{reset:<{name_indent}}({reset:<{name_indent + 1}}),\n"
        for port_name in ports:
            if port_name in (clock, reset):
                continue
            miter_str += f"    .{port_name:<{name_indent}}({port_name + '_' + str(i + 1):<{name_indent + 1}}),\n"
        miter_str = miter_str[:-2] + "\n  );\n\n"

    miter_str += "endmodule\n"

    return miter_str


def print_sv_comment_separator(header: str, indent: int = 2):
    sep_str = f"{' ' * indent}  // {'=' * len(header)} //\n"
    sep_str += f"{' ' * indent} // {header} //\n"
    sep_str += f"{' ' * indent}// {'=' * len(header)} //\n\n"
    return sep_str


def print_tcl_comment_separator(header: str, indent: int = 0):
    sep_str = f"{' ' * indent}{'#' * (len(header) + 4)}\n"
    sep_str += f"{' ' * indent}# {header} #\n"
    sep_str += f"{' ' * indent}{'#' * (len(header) + 4)}\n\n"
    return sep_str


def print_property(property_name: str, antecedent: str, consequent: str, reset: str = "", active_high: bool = True):
    disable_str = f"disable iff ({'' if active_high else '!'}{reset}) " if reset else ""
    property_str = f"  property {property_name}_p;\n"
    property_str += f"    {antecedent}\n"
    property_str += f"  implies\n"
    property_str += f"    {consequent};\n"
    property_str += f"  endproperty\n"
    property_str += f"  {property_name}_p_a: assert property ({disable_str}{property_name}_p);\n\n\n"

    return property_str


def print_bind_statement(
    miter_circuit_name: str,
    signals_list: list[str],
    reset: str | None,
    reset_active_high: bool
):

    bind_expr = lambda sig: f"!{sig}" if sig == reset and not reset_active_high else sig
    valid_signals = filter(None, [reset] + signals_list)
    ports = ", ".join(f".{sig}({bind_expr(sig)})" for sig in valid_signals)
    return f"bind {miter_circuit_name} property_checker checker_bind({ports});\n\n"
