"""Module providing CEX analysis and data structures."""
from collections import deque
from io import StringIO


class VcdVariable:
    """Class bundling information about a VCD variable."""

    def __init__(self, var_type: str, size: int, var_id: str, name: str, range: str):
        self.type: str = var_type
        self.size: int = size
        self.id: str = var_id
        self.name: str = name
        self.range: str = range


class VcdScope:
    """Class representing a VCD scope (module, function, ...)"""

    id_to_var: dict[str, VcdVariable] = {}
    """Dictionary mapping variable IDs to their corresponding VcdVariable objects. Explicitly saved to increase performance."""

    def __init__(self, scope_type: str, name: str):
        self.type: str = scope_type
        self.name: str = name
        self.subscopes: list[VcdScope] = []
        self.variables: list[VcdVariable] = []

    def add_var(self, var: VcdVariable):
        self.variables.append(var)

    def add_subscope(self, scope):
        self.subscopes.append(scope)

    def get_var_by_id(self, var_id: str) -> VcdVariable:
        if var_id in self.id_to_var:
            return self.id_to_var[var_id]
        raise ValueError("Variable not found. Variable ID:" + var_id)

    def find_var_by_name(self, var_name: str) -> VcdVariable:
        queue = deque([self])
        while queue:
            current_scope = queue.popleft()
            for var in current_scope.variables:
                if var.name == var_name:
                    return var
            queue.extend(current_scope.subscopes)
        raise ValueError("Variable not found. Variable name: " + var_name)

    def find_subscope_by_name(self, subscope_name: str):
        for scope in self.subscopes:
            if scope.name == subscope_name:
                return scope
        raise ValueError(
            f"Subscope {subscope_name} not found in scope {self.name}.")


class VcdMeta:
    """Class bundling VCD metadata information."""

    def __init__(self):
        self.date: str = ""
        self.version: str = ""
        self.timescale: str = ""
        self.comments: list[str] = []


def read_tokens_until_end(file: StringIO, tokens: list[str]) -> list[str]:
    """Read tokens from the given file until an $end token is found"""
    while "$end" not in tokens:
        tokens += file.readline().split()
    return tokens


def parse_metadata(file: StringIO, tokens: list[str]) -> tuple[list[str], str]:
    """Parses $date, $version, $comment and $timescale tokens in the VCD file

    :param file: Uploaded VCD file
    :param tokens: Currently read tokens after the start token

    :return: Updated token list after $end and a string with the extracted metadata"""
    tokens = read_tokens_until_end(file, tokens)
    i = tokens.index("$end")
    parsed_str = " ".join(tokens[1:i])
    return tokens[i + 1:], parsed_str


def parse_var(file: StringIO, tokens: list[str]) -> tuple[list[str], VcdVariable | None]:
    """Parses $var tokens in the VCD file

    :param file: Uploaded VCD file
    :param tokens: Currently read tokens after the start token

    :return: Updated token list after $end and the extracted VcdVariable"""
    tokens = read_tokens_until_end(file, tokens)

    var = VcdVariable(
        var_type=tokens[1],
        size=int(tokens[2]),
        var_id=tokens[3],
        name=tokens[4],
        range=tokens[5]
    )
    VcdScope.id_to_var[var.id] = var

    """There can be an optional width like [31:0] after the variable name. We don't use this currently."""
    tokens = tokens[tokens.index("$end") + 1:]
    return tokens, var


def parse_scope(file: StringIO, tokens: list[str]) -> tuple[list[str], VcdScope]:
    """
    Parses the scope structure from a VCD (Value Change Dump) file and builds a hierarchical
    representation of the scope, handling nested scopes and declared variables.

    This function processes the VCD content by reading lines and tokenizing them to identify
    different VCD commands such as `$scope`, `$upscope`, `$var`, and `$end`. It creates a
    `VcdScope` object for each scope and populates it with variables and sub-scopes recursively.

    :param file: The input file-like object from which the VCD data is read.
    :param tokens: The list of current tokens already read and ready for parsing.
    :type tokens: list[str]
    :return: A tuple containing the list of remaining tokens after parsing and the parsed
             scope object representing the hierarchical structure.
    :rtype: tuple[list[str], VcdScope]
    :raises ValueError: If an unknown command or value is encountered while parsing.
    """
    tokens = read_tokens_until_end(file, tokens)
    scope = VcdScope(scope_type=tokens[1], name=tokens[2])
    tokens = tokens[4:]
    while True:
        if not tokens:
            tokens += file.readline().split()
        elif tokens[0] == "$var":
            tokens, var = parse_var(file, tokens)
            scope.add_var(var)
        elif tokens[0] == "$scope":
            tokens, subscope = parse_scope(file, tokens)
            scope.add_subscope(subscope)
        elif tokens[0] == "$upscope":
            tokens = read_tokens_until_end(file, tokens)
            return tokens[2:], scope
        else:
            raise ValueError(f"Unknown command/value: {tokens[0]}")


def parse_value_changes(file: StringIO, tokens: list[str]) -> dict[int, dict[str, str]]:
    """Parse value changes section of the given VCD file"""
    time = 0
    value_changes = {0: {}}

    while True:
        line = file.readline()
        if not line:  # End of File
            break

        tokens += line.split()
        current_token = tokens[0]

        if current_token[0] == "$":
            raise NotImplementedError("$dump... functions not implemented")

        if current_token[0] == "r":
            raise NotImplementedError("real variables not implemented")

        # timestamp
        if current_token[0] == "#":
            time = int(current_token[1:])
            value_changes[time] = {}
            tokens = tokens[1:]

        # single-bit variable change
        elif current_token[0] in "01xXzZ":
            var_val = current_token[0]
            var_id = current_token[1:]
            value_changes[time][var_id] = var_val
            tokens = tokens[1:]

        # multi-bit variable change
        elif current_token[0] == "b":
            var_val = current_token[1:]
            var_id = tokens[1]
            missing_bits = VcdScope.id_to_var[var_id].size - len(var_val)
            if missing_bits > 0:
                if var_val[0] == "1":
                    var_val = missing_bits * "0" + var_val
                else:
                    var_val = missing_bits * var_val[0] + var_val
            value_changes[time][var_id] = var_val
            tokens = tokens[2:]

    return value_changes


def parse_vcd_file(file: StringIO):
    """
    Parses a VCD (Value Change Dump) file and extracts the hierarchical structure, value changes,
    and metadata. The function expects the file to conform to the VCD specification requiring
    exactly one top-level module.

    :param file: The input file-like object that must conform to the VCD file format.
    :type file: UploadedFile
    :return: A tuple containing the main scope, signal value changes over time,
             and VCD metadata object
    :rtype: (VcdScope, Dict[int, Dict[str, str]], VcdMeta)
    :raises ValueError: If the VCD format does not have exactly one top-level module.
    :raises NotImplementedError: If unsupported constructs are encountered.
    """
    tokens = []
    scopes = []
    meta = VcdMeta()
    structure_parsed = False
    while not structure_parsed:
        if not tokens:
            tokens += file.readline().split()
        elif tokens[0] == "$date":
            tokens, date = parse_metadata(file, tokens)
            meta.date = date
        elif tokens[0] == "$version":
            tokens, version = parse_metadata(file, tokens)
            meta.version = version
        elif tokens[0] == "$comment":
            tokens, comment = parse_metadata(file, tokens)
            meta.comments.append(comment)
        elif tokens[0] == "$timescale":
            tokens, timescale = parse_metadata(file, tokens)
            meta.timescale = timescale
        elif tokens[0] == "$scope":
            tokens, scope = parse_scope(file, tokens)
            scopes.append(scope)
        elif tokens[0] == "$enddefinitions":
            tokens = read_tokens_until_end(file, tokens)
            tokens = tokens[2:]
            structure_parsed = True

    if len(scopes) != 1:
        raise ValueError(
            "VCD format not supported, there must be exactly one top module.")

    value_changes = parse_value_changes(file, tokens)

    file.close()

    return scopes[0], value_changes, meta


def identify_instances(scope: VcdScope) -> tuple[str, str]:
    """Identifies the two instances of the miter circuit in the parsed VcdScope object"""
    if len(scope.subscopes) != 3:
        return "", ""
    # Iterates through subscopes then variables and use set to ignore the order of variables
    subscope = []
    for sub in scope.subscopes:
        wire_names = set(var.name for var in sub.variables)
        subscope.append((sub.name, wire_names))

    # [0][0] instance name for 0 item / [0][1] wire names for 0 item
    if subscope[0][1] == subscope[1][1]:
        instances = [subscope[0][0], subscope[1][0]]
    elif subscope[1][1] == subscope[2][1]:
        instances = [subscope[1][0], subscope[2][0]]
    elif subscope[2][1] == subscope[0][1]:
        instances = [subscope[0][0], subscope[2][0]]
    else:
        instances = ["", ""]
    return instances[0], instances[1]


def find_pairs(scope_a: VcdScope, scope_b: VcdScope, pairs: dict[str, str], var_names: dict[str, str], prefix="") -> None:
    """
    Finds and establishes a mapping of variables and subscopes between two VCD (Value Change Dump) scopes.

    This function iterates over variables contained in the first scope, matches them with variables
    in the second scope by name, and creates a mapping of their unique identifiers in the `pairs` dictionary.
    It also builds a hierarchical mapping of variable names (with prefixes) and stores them in the `var_names` dictionary.

    :param scope_a: First VCD scope to compare, containing variables and subscopes.
    :type scope_a: VcdScope
    :param scope_b: Second VCD scope to compare, containing variables and subscopes.
    :type scope_b: VcdScope
    :param pairs: Dictionary to store the mapping of variable IDs between `scope_a` and `scope_b`.
    :type pairs: dict[str, str]
    :param var_names: Dictionary to store hierarchical prefixed variable names derived from the scopes.
    :type var_names: dict[str, str]
    :param prefix: Prefix string added to variable names to denote hierarchy. Defaults to an empty string.
    :type prefix: str, optional
    :return: None
    """
    for var_a in scope_a.variables:

        # FIXME
        """JasperGold generates unique names for signals in functions that are different between the two instances.
        For example, ":func_pushpop_reg_length_0:rlist4" and ":func_pushpop_reg_length_1:rlist4"
        We currently ignore them.
        """
        if ":" in var_a.name:
            continue

        var_b = scope_b.find_var_by_name(var_a.name)
        pairs[var_a.id] = var_b.id
        pairs[var_b.id] = var_a.id
        var_names[var_a.id] = prefix + "." + \
            var_a.name if prefix else var_a.name
    for subscope_a in scope_a.subscopes:
        subscope_b = scope_b.find_subscope_by_name(subscope_a.name)
        new_prefix = prefix + "." + subscope_a.name if prefix else subscope_a.name
        find_pairs(subscope_a, subscope_b, pairs, var_names, new_prefix)


def find_value_deviations(value_changes: dict[int, dict[str, str]], pairs: dict[str, str], var_names: dict[str, str]) -> tuple[
        dict[int, list[str]], dict[int, list[str]]]:
    """
    Analyzes the changes in variable values over time to identify deviations, classified
    by individual variables and timestamps. The function checks if variable pairs deviate
    from their expected synchronized behavior and categorizes their deviations into lists.

    :param value_changes: A dictionary where keys represent timestamps (int), and values
        are dictionaries mapping variable names (str) to their new values (str).
    :param pairs: A dictionary mapping the names of variables (str) to the names of their
        corresponding paired variables (str).
    :param var_names: A dictionary mapping variable names (str) to their human-readable
        descriptive names (str). Used to resolve variable names to a consistent identifier.
    :return: A tuple containing two elements:
        - A dictionary where keys represent timestamps (int), and values are lists of
          deviated variables (list[str]) corresponding to that timestamp.
        - A dictionary where keys represent timestamps (int), and values are lists of
          variables (list[str]) that deviated for the first time at that timestamp.
    """
    deviated_vars = []
    deviations_by_time = {}
    first_deviations_by_time = {}
    for timestamp, changes in value_changes.items():
        deviations_by_time[timestamp] = []
        first_deviations_by_time[timestamp] = []
        for changing_var, val in changes.items():
            if changing_var not in pairs:
                continue
            paired_var = pairs[changing_var]
            var_a = changing_var if changing_var in var_names else paired_var
            # Either both variables change to different values or only one variable changes
            if not (paired_var in changes and val == changes[paired_var]):
                if var_a not in deviated_vars:
                    deviated_vars.append(var_a)
                    first_deviations_by_time[timestamp].append(var_a)
                if var_a not in deviations_by_time[timestamp]:
                    deviations_by_time[timestamp].append(var_a)

    return deviations_by_time, first_deviations_by_time


def analyze_cex(scope: VcdScope, value_changes: dict[int, dict[str, str]], instance_1_name: str, instance_2_name: str):
    """Main function that identifies signal deviations."""
    instance_1 = scope.find_subscope_by_name(instance_1_name)
    instance_2 = scope.find_subscope_by_name(instance_2_name)
    pairs = {}
    var_names = {}
    find_pairs(instance_1, instance_2, pairs, var_names)
    deviations_by_time, first_deviations_by_time = find_value_deviations(
        value_changes, pairs, var_names)
    return pairs, var_names, deviations_by_time, first_deviations_by_time
