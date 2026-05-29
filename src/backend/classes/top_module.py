"""Classes that manage the structure of top modules and their associated operations."""
from collections import deque
from collections.abc import Iterator

from src.backend.classes.subclasses import Signal, Port, Instantiation, Parameter
from src.backend.shortest_path import shortest_path
from src.constants import INPUT, OUTPUT, INOUT, FANOUT
from src.utils import sort_signals_hierarchically, sort_names_by_keywords


class TopModule:
    """This class defines how a Verilog top module is stored. Every signal, instantiation and parameter
    is stored with its complete path, which makes further nesting of classes unnecessary."""

    def __init__(self):
        """The constructor creates an empty graph (**signals:** nodes, **fanout/fanin:** edges) and additional sets of signal names
        (**states**, **nets**, ...) for quick access and quick characterization."""
        #TODO: Change signals from dict to list, saving the name in the Signal object
        #TODO: Remove redundant nets, states, ports sets
        self.__signals: dict[str, Signal | Port] = {}
        self.__fanout: dict[str, set[str]] = {}
        self.__fanin: dict[str, set[str]] = {}
        self.__states: set[str] = set()
        self.__nets: set[str] = set()
        self.__ports: set[str] = set()
        self.__event_triggers: set[str] = set()
        self.conditions: set[str] = set()
        self.__instantiations: dict[str, Instantiation] = {}
        self.__parameters: dict[str, Parameter] = {}
        self.__filename: str

    def add_instantiation(self, module: str, instance: str):
        """Adds an instantiation.

        Args:
            module: Module that is instantiated
            instance: Name of the instance
        """
        self.__instantiations[instance] = Instantiation(module, instance)

    def has_instance(self, instance: str) -> bool:
        """Checks whether an instantiation is present.
        Args: module: Module that is instantiated
        instance: Name of the instance
        """
        return instance in self.__instantiations

    def add_connection(self, instance: str, top_signal: str, instance_signal: str, direction: int):
        """Adds a connection to an instantiation.

        Args:
            instance: Name of the instance
            top_signal: Signal of the upper module
            instance_signal: Signal of the instance
            direction: OUTPUT / INPUT / INOUT
        """
        for t in top_signal:
            if direction == OUTPUT:
                self.add_edge(instance_signal, t)
                self.__instantiations[instance].connections.add((instance_signal, t))
            elif direction == INPUT:
                self.add_edge(t, instance_signal)
                self.__instantiations[instance].connections.add((t, instance_signal))
            elif direction == INOUT:
                # conservative: both directions
                self.add_edge(t, instance_signal)
                self.add_edge(instance_signal, t)
                self.__instantiations[instance].connections.add((t, instance_signal))
                self.__instantiations[instance].connections.add((instance_signal, t))
            else:
                # Unknown: treat as INOUT or skip; I'd do INOUT for now
                self.add_edge(t, instance_signal)
                self.add_edge(instance_signal, t)
                self.__instantiations[instance].connections.add((t, instance_signal))
                self.__instantiations[instance].connections.add((instance_signal, t))


    def add_parameter(self, parameter: str, parameter_type: str, parameter_value: str, is_overwritten: bool):
        """Adds a parameter.

        Args:
            parameter: Name of the parameter
            parameter_type: Type of the parameter
            parameter_value: Value of the parameter
            is_overwritten: Whether parameter is overwritten
        """
        self.__parameters[parameter] = Parameter(parameter_type, parameter_value, is_overwritten)

    def get_parameters(self) -> dict[str, Parameter]:
        return self.__parameters

    def get_instantiations(self) -> dict[str, Instantiation]:
        return self.__instantiations

    def get_instations_of_instance(self, instance: str) -> set[Instantiation]:
        """Returns set of all instantiations in given instance"""

        sub_instances: set[Instantiation] = set()

        for inst_name, inst in self.get_instantiations().items():
            # Verify hierarchy via name string composition
            if inst_name.startswith(instance+"."): 
                sub_instances.add(inst)

        return sub_instances

    def get_ports_of_instance(self, instance_name: str) -> set[Port]:
        """Returns set of all Ports in given instance."""

        ports: set[Port] = set()

        instance: Instantiation | None = self.__instantiations.get(instance_name)

        # Return empty set when instance name doesn't map to valid instance object
        if instance is not None:
            
            for source,destination in instance.connections:
                port: Signal | Port | None = None
                if source.startswith(instance_name):
                    port = self.__signals[source]
                elif destination.startswith(instance_name):
                    port = self.__signals[destination]
                
                # only return ports
                if type(port) is Port:
                    ports.add(port)        
            
        return ports

    def get_submodule_names(self) -> set[str]:
        """Returns a set of all submodules used in this TopModule

        Returns:
            submodules: Set of module names.
        """
        submodules = set()
        for inst_name, inst in self.get_instantiations().items():
            submodules.add(inst.module)
        return submodules

    def add_signal(self, name: str, signal_type: str, signal_width: int):
        """Adds a signal to the graph and default categorizes the signal as a net signal.

        Args:
            name: Name of the port
            signal_type: Type of the signal
            signal_width: Bit width of the signal
        """
        if name not in self.__signals:
            self.__signals[name] = Signal(name, signal_type, signal_width)
            self.__fanout[name] = set()
            self.__fanin[name] = set()
        self.__nets.add(name)

    def add_port(self, name: str, port_type: str, port_direction, port_width: int):
        """Adds a port to the graph and categorizes the signal as a port signal.

        Args:
            name: Name of the port
            port_type: Type of the port
            port_direction: Directions of the port (**True:** Output | **False:** Input | **inout** Inout | None )
            port_width: Bit width of the port
        """
        if name not in self.__signals:
            self.__signals[name] = Port(name, port_type, port_direction, port_width)
            self.__fanout[name] = set()
            self.__fanin[name] = set()
            self.__ports.add(name)
        else:
            raise Exception(f'Adding duplicate port: {name}')

    def add_edge(self, source: str, target: str):
        """Sets a fan-in and a fan-out edge between two signals.

        Args:
            source: Name of the source signal
            target: Name of the target signal
        """
        if source not in self.__fanout:
            raise Exception(f'Source Signal not found: {source} -> {target}')
        if target not in self.__fanin:
            raise Exception(f'Target Signal not found: {source} -> {target}')
        self.__fanout[source].add(target)
        self.__fanin[target].add(source)

    def set_state(self, name: str):
        """Changes the signal type from the default net type to a state type.

        Args:
            name: Name of the state signal
        """
        self.__states.add(name)
        if name in self.__nets:
            self.__nets.remove(name)

    def set_event_trigger(self, name: str):
        """Additionally categorizes the signal as an event_trigger signal.

        Args:
            name: Name of the event_trigger signal
        """
        if name not in self.__signals:
            raise Exception(f'Event trigger signal not found: {name}')
        self.__event_triggers.add(name)

    def set_condition(self, name: str):
        """Additionally categorizes the signal as a condition signal.

        Args:
            name: Name of the state signal
        """
        if name not in self.__signals:
            raise Exception(f'Condition signal not found: {name}')
        self.conditions.add(name)

    def is_state(self, signal: str) -> bool:
        return signal in self.__states

    def is_port(self, signal: str) -> bool:
        return signal in self.__ports

    def get_signals(self) -> dict[str, Signal | Port]:
        return self.__signals

    def has_signal(self, signal: str) -> bool:
        return signal in self.__signals

    def get_states(self, full: bool = False) -> list[str] | dict[str, Signal]:
        if full:
            return {key: self.__signals[key] for key in sort_signals_hierarchically(self.__states)}
        else:
            return sort_signals_hierarchically(self.__states)

    def get_nets(self, full: bool = False) -> list[str] | dict[str, Signal]:
        if full:
            return {key: self.__signals[key] for key in sort_signals_hierarchically(self.__nets)}
        else:
            return sort_signals_hierarchically(self.__nets)

    def get_event_triggers(self) -> list[str]:
        return sort_signals_hierarchically(self.__event_triggers)

    def get_conditions(self) -> list[str]:
        return sort_signals_hierarchically(self.conditions)

    def get_root_signals(self, signals: set[str]) -> list[str]:
        """Finds all signals that influence the given set of signals but are not influenced by any other signals.

        Args:
            signals: Set of signal names

        Returns:
            List of root signal names
        """
        fanin = self.__fanin
        roots = []
        visited = set()

        for signal in signals:
            if signal in visited:
                continue

            stack = [signal]

            while stack:
                fan_in_signal = stack.pop()
                if fan_in_signal in visited:
                    continue

                visited.add(fan_in_signal)
                if fanin[fan_in_signal]:
                    stack.extend(fanin[fan_in_signal])
                else:
                    roots.append(fan_in_signal)

        return roots

    def get_clocks(self) -> list[str]:
        """Gets the root signals of the event_triggers and sorts them based on the clock-like substring property.

        Returns:
            Ordered list of clock signal names
        """
        signals = self.get_root_signals(self.__event_triggers)
        return sort_names_by_keywords(signals, ["clk", "clock"])

    def get_resets(self) -> list[str]:
        """Gets the root signals of the conditions and sorts them based on the reset-like substring property.

        Returns:
            Ordered list of reset signal names
        """
        signals = self.get_root_signals(self.conditions)
        return sort_names_by_keywords(signals, ["rst", "reset"])

    def get_all_ports(self, full: bool = False) -> list[str] | dict[str, Signal]:
        if full:
            return {key: self.__signals[key] for key in sort_signals_hierarchically(self.__ports)}
        else:
            return sort_signals_hierarchically(self.__ports)

    def get_primary_ports(self, full: bool = False) -> list[str] | dict[str, Signal]:
        return self._get_primary_ports_by_direction(direction=None, full=full)

    def get_primary_inputs(self, full: bool = False) -> list[str] | dict[str, Signal]:
        return self._get_primary_ports_by_direction(direction=INPUT, full=full)

    def get_primary_outputs(self, full: bool = False) -> list[str] | dict[str, Signal]:
        return self._get_primary_ports_by_direction(direction=OUTPUT, full=full)

    def get_primary_inouts(self, full: bool = False):
        return self._get_primary_ports_by_direction(direction=INOUT, full=full)

    def _get_primary_ports_by_direction(self, direction: None | int, full: bool) -> list[str] | dict[str, Signal]:
        primary_port_names = [port_name for port_name in self.__ports if '.' not in port_name]

        if direction is not None:
            primary_port_names = [
                port_name for port_name in primary_port_names
                if self.__signals[port_name].direction == direction
            ]

        sorted_ports = sort_signals_hierarchically(primary_port_names)

        if full:
            return {key: self.__signals[key] for key in sorted_ports}
        return sorted_ports

    def get_fanin_of_signal(self, signal: str) -> set[str]:
        return self.__fanin[signal]

    def get_fanout_of_signal(self, signal: str) -> set[str]:
        return self.__fanout[signal]

    def reachable_signals(self, source: str, fan_direction: bool) -> Iterator[str]:
        """Yields all reachable signals based on the source signal.

        Args:
            source: Name of source signal
            fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)

        Yields:
            Next reachable signal
        """
        fan_dict = self.__fanout if fan_direction == FANOUT else self.__fanin

        seen_signals = set(source)
        to_process = [source]

        yield source

        while to_process:
            current_fan_level = to_process
            to_process = []
            for signal in current_fan_level:
                for neighbor in fan_dict[signal]:
                    if neighbor not in seen_signals:
                        seen_signals.add(neighbor)
                        to_process.append(neighbor)
                        yield neighbor
                # Exit early if all signals have been seen
                if len(seen_signals) == len(fan_dict):
                    return

    def shortest_path(self, source: str, target: str, fan_direction: bool):
        """
            Wrapper function that delegates the implementation to shortest_path
        """
        # TO DO : To remove from the Top Module
        return shortest_path(
            self.__fanin,
            self.__fanout,
            source,
            target,
            fan_direction
        )

    def get_fan_subgraph(self, source: str, depth: int, fan_direction: bool, only_state: bool) -> Iterator[str, str]:
        """Analyzes the graph and yields the desired fan-in/fan-out subgraph based on the given parameters.

        Args:
            source: Name of the source signal
            depth: Number of cycles to be analyzed
            fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)
            only_state: **True:** Returns only state signals | **False:** Returns all signals

        Yields:
            Source and target of onSignale edge of the new subgraph
        """
        if fan_direction:
            adj_list = self.__fanout
        else:
            adj_list = self.__fanin

        #############################################
        # NEW: full-cone mode when only_state is OFF
        #############################################
        if not only_state:
            # (node, cycles_crossed)
            q = deque([(source, 0)])
            visited = set([(source, 0)])

            while q:
                cur, cycles = q.popleft()
                if cycles > depth:
                    continue

                for nxt in adj_list.get(cur, []):
                    # report the edge we actually traversed
                    if fan_direction:
                        yield cur, nxt
                    else:
                        yield nxt, cur

                    # crossing a state counts as one "cycle"
                    nxt_cycles = cycles + (1 if self.is_state(nxt) else 0)
                    key = (nxt, nxt_cycles)
                    if nxt_cycles <= depth and key not in visited:
                        visited.add(key)
                        q.append((nxt, nxt_cycles))
            return

        visited = {source}
        queue = deque([(source, 1, iter(adj_list[source]))])
        while queue:
            parent, cycle_now, children = queue[0]
            try:
                child = next(children)
                if child not in visited:
                    visited.add(child)
                    if not self.is_state(child):
                        queue.append((parent, cycle_now, iter(adj_list[child])))
                    else:
                        if fan_direction:
                            if only_state:
                                yield parent, child
                            else:
                                for a, b in self.shortest_path(parent, child, fan_direction):
                                    yield a, b
                        else:
                            if only_state:
                                yield child, parent
                            else:
                                for a, b in self.shortest_path(child, parent, fan_direction):
                                    yield a, b
                        if cycle_now < depth:
                            queue.append((child, cycle_now + 1, iter(adj_list[child])))
            except StopIteration:
                queue.popleft()

    def get_fan_nodes(self, source: str, depth: int, fan_direction: bool, only_state: bool) -> set[str]:
        """Analyzes the graph and yields the desired fan-in/fan-out nodes based on the given parameters.

        Args:
            source: Name of the source signal
            depth: Number of cycles to be analyzed
            fan_direction: Direction of the analysis (**True:** Fan-out | **False:** Fan-in)
            only_state: **True:** Returns only state signals | **False:** Returns all signals

        Returns:
            Set of nodes that lie in the fan-in/fan-out of the given source signal.
        """
        edges = list(self.get_fan_subgraph(source, depth, fan_direction, only_state))
        return {source} | set(node for edge in edges for node in edge)
