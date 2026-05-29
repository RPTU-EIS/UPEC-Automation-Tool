"""Utility module with functions for the backend."""

import re


def compute_width_from_type_str(type_str: str) -> int:
    """Parses the signal type given by Pyslang and computes the effective bit width.

    :param type_str: Type string extracted by Pyslang

    :return: Width of the signal"""
    enum_type_width = re.findall(r"enum{\w+=(\d+)'", type_str)
    width = int(enum_type_width[0]) if enum_type_width else 1

    for range_match in re.findall(r"\[(\d+):(\d+)]", type_str):
        i_low, i_high = sorted(map(int, range_match))
        width *= i_high - i_low + 1

    return width


def format_type_str(type_str: str) -> tuple[str, str]:
    """
    Converts the type string given by Pyslang into a printable representation.

    "reg" is converted to "logic".
    Whitespace is inserted to make it look more nicely.
    For enums, if it is taken from a package, we will reuse that definition as the type.
    If not, the full enum definition will be returned.
    Suffixes for unpacked arrays are given separately. See also:
    https://verificationguide.com/systemverilog/systemverilog-packed-and-unpacked-array/

    Possible examples of input strings:
        reg
        reg[7:0]
        logic
        logic[31:0]
        logic[31:0][3:0]
        logic[31:0]$[0:1] -> caused by "logic [31:0] mySignal[2];"
        logic signed[32:0]
        enum{MD_OP_MULL=2'd0,MD_OP_MULH=2'd1,MD_OP_DIV=2'd2,MD_OP_REM=2'd3}ibex_pkg::md_op_e
        enum{IDLE=2'd0,DIVIDE=2'd1,FINISH=2'd2}serdiv.e$15 -> caused by "enum logic [1:0] {IDLE, DIVIDE, FINISH} mySignal;"
        enum{ALBL=2'd0,ALBH=2'd1,AHBL=2'd2,AHBH=2'd3}ibex_multdiv_fast.gen_mult_fast.mult_fsm_e

    :param type_str: String representation of the type as given by Pyslang

    :return: Tuple of the formated type string and a sting containing the unpacked suffix
    """

    unpacked_suffix = ""
    if "$" in type_str:
        type_str, suffix_str = type_str.rsplit("$", 1)
        unpacked_match = re.findall(r"(\[\d+:\d+])", suffix_str)
        if unpacked_match:
            unpacked_suffix = unpacked_match[0]

    if "enum" in type_str:
        enum_def, enum_name = re.findall(r"(enum\{\S+})(\S+)", type_str)[0]
        type_str = enum_name if "::" in enum_name else enum_def

    type_str = type_str.replace("reg", "logic")
    type_str = type_str.replace("[", " [")
    type_str = type_str.replace("{", " {")
    type_str = type_str.replace(",", ", ")

    return type_str, unpacked_suffix
