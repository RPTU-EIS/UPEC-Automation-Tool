from src.backend.backend_utils import compute_width_from_type_str, format_type_str
from src.constants import INPUT, OUTPUT, INOUT


class Signal:
    """This class defines how a signal is stored. Signals are nodes in the main graph."""

    def __init__(self, signal_name: str, signal_type: str, signal_width: int = 0) -> None:
        self.name: str = signal_name
        self.type_str: str = ""
        self.unpacked_suffix: str = ""
        self.type_str, self.unpacked_suffix = format_type_str(signal_type)
        self.width: int = signal_width
        if self.width == 0:
            self.width = compute_width_from_type_str(signal_type)

    def __str__(self) -> str:
        return f"{self.type_str} {self.name} {self.unpacked_suffix}".strip()


class Port(Signal):
    """This class defines how a port is stored. Ports are nodes in the main graph."""

    def __init__(self, port_name: str, port_type: str, port_direction: int, port_width: int) -> None:
        super().__init__(port_name, port_type, port_width)
        self.direction = port_direction # can be INPUT/OUTPUT/INOUT/None

    def __str__(self) -> str:
        dir_map = {
            INPUT: "input",
            OUTPUT: "output",
            INOUT: "inout",
        }
        direction_str = dir_map.get(self.direction, "unknown")
        return f"{direction_str} {self.type_str} {self.name} {self.unpacked_suffix}".strip()


class Instantiation:
    """This class defines how an instantiation of a Verilog module is stored."""

    def __init__(self, module: str, instance: str):
        self.module: str = module
        self.instance: str = instance
        self.connections: set[tuple[str, str]] = set()


class Parameter:
    """This class defines how parameters of a Verilog module are stored."""

    def __init__(self, parameter_type: str, parameter_value: str, is_overridden: bool):
        self.type: str = parameter_type
        self.value: str = parameter_value
        self.is_overridden: bool = is_overridden
