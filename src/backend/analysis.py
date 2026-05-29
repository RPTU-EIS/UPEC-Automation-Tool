import re
from collections.abc import Iterator
from copy import deepcopy

import pyslang.ast as ast
import pyslang.pyslang as pyslang
import pyslang.syntax as syntax

from src.backend.backend_visitors.connect_visitor import ConnectVisitor
from src.backend.backend_visitors.declare_visitor import DeclareVisitor
from src.backend.backend_visitors.scan_visitor import ScanVisitor
from src.backend.classes.top_module import TopModule
from src.backend.top_module_manager import TopModuleManager
from src.constants import INPUT, OUTPUT, INOUT, UNKNOWN


def create_pyslang_compilation(file_paths):
    """
    Create a pyslang 11 Compilation object from one or more source files.
    """

    if isinstance(file_paths, str):
        file_paths = [file_paths]

    file_paths = [str(p) for p in file_paths]

    compilation = ast.Compilation()

    for file_path in file_paths:
        syntax_tree = syntax.SyntaxTree.fromFile(file_path)
        compilation.addSyntaxTree(syntax_tree)

    syntax_trees = compilation.getSyntaxTrees()
    if not syntax_trees:
        raise RuntimeError("pyslang did not create any syntax trees.")

    source_manager = syntax_trees[0].getDefaultSourceManager()

    return compilation, source_manager

def compute_diagnostic(compilation, source_manager):
    """Computes diagnostic data from pyslang compilation object.

       :param compilation : Pyslang compilation object
       :param source_manager : source manager given by compilation object

       :return: tuple of diagnostic data"""
    diagnostic_client = pyslang.TextDiagnosticClient()
    diagnostic_engine = pyslang.DiagnosticEngine(source_manager)
    diagnostic_engine.addClient(diagnostic_client)
    for diagnosis in compilation.getAllDiagnostics():
        diagnostic_engine.issue(diagnosis)
    return diagnostic_engine.numErrors, diagnostic_engine.numWarnings, diagnostic_client.getString()

def extract_assertions(root):
    """Extracts immediate assertions from pyslang syntax tree root node.

       :param root : Pyslang syntax tree root node

       :return: list of assertions"""
    assertions = []
    iterables = {'SyntaxList','TokenList','ConditionalStatement','EventControlWithExpression','SequentialBlockStatement'}
    def visitor(node):
        """Node parser for pyslang objects, can take both syntax tree object or compilation object.

           :param node : Pyslang node"""
        if node.kind.name == 'ImmediateAssertStatement':
            location = f"Line {node.sourceRange.start}, Column {node.sourceRange.end}"
            assertion_text = str(node)
            assertions.append((location, assertion_text))
        elif hasattr(node, 'members'):
            for member in node.members:
                visitor(member)
        elif node.kind.name in iterables:
            for obj in node:
                visitor(obj)
        elif hasattr(node, 'statement'):
            for obj in node.statement:
                visitor(obj)
        elif hasattr(node, 'portConnections'):
            visitor(node)
        elif hasattr(node, 'body'):
            for child in node.body:
                visitor(child)
    visitor(root)

    return assertions


class Analysis:
    """This class encapsulates creating and analysing syntax trees from pyslang compilation object"""

    def __init__(self, file_paths):
        """The constructor analyzes creates syntax tree from pyslang compilation object and anlyses the same.

        Args:
            file_paths: file paths of the verilog files
        """
        self._compilation, self._source_manager = create_pyslang_compilation(file_paths)

        self._diagnostic_data = compute_diagnostic(self._compilation, self._source_manager)
        self._top_instances = self._compilation.getRoot().topInstances
        self.module = TopModule()
        self.re_pattern = None
        self._ignored = {
            ast.SubroutineSymbol,
            ast.StatementBlockSymbol,
            ast.TypeAliasType,
            ast.UninstantiatedDefSymbol,
            ast.WildcardImportSymbol,
            ast.TransparentMemberSymbol,
            ast.EmptyStatement,
            ast.ConcurrentAssertionStatement,
            ast.ImmediateAssertionStatement,
        }
        self._project = self.compute_project()


    def compute_project(self):
        top_modules = {}
        for top_instance in self._top_instances:
            self.module = TopModule()
            top_modules[top_instance.name] = self.module
            self.module.filename = str(self._source_manager.getFileName(top_instance.location))
            self.re_pattern = re.escape(top_instance.name + ".") + r'\b'

            decl = DeclareVisitor(self)
            scan = ScanVisitor(self)
            conn = ConnectVisitor(self)

            decl.visit(top_instance, set())
            scan.visit(top_instance, set())
            conn.visit(top_instance, set())

        return TopModuleManager(top_modules, self._diagnostic_data)

    def _get_project(self):
        return self._project

    project = property(_get_project)

    def get_name(self, node):
        """Gets a formatted name from the hierarchical path of a node.

        Returns:
            str: The formatted name derived from the hierarchical path.
        """
        path = node.hierarchicalPath
        path = re.sub(self.re_pattern, '', path)
        return path


    def _map_pyslang_port_dir(self, port_symbol) -> int:
        d = getattr(getattr(port_symbol, "direction", None), "value", None)
        if d is None:
            return UNKNOWN
        if d in (INPUT, OUTPUT, INOUT):
            return int(d)
        return UNKNOWN

    def _get_member_owner_bases(self, expr):
        """Return the expression base(s) that structurally own a member access.

        Example For indexed member access:
            ifc.req.data           -> ifc.req
            A[B].field             -> A
        """
        if isinstance(expr, ast.ElementSelectExpression):
            yield from self.get_short_expr(expr.value)
            return

        yield from self.get_short_expr(expr)

    def _get_extra_expr_dependencies(self, expr):
        """Return extra dependency expressions carried by wrappers.

        Example:
            struct[element].field -> element
        """
        if isinstance(expr, ast.ElementSelectExpression):
            yield from self.get_short_expr(expr.selector)

    def get_short_expr(self, expr) -> Iterator[str]:
        """returns a simplified view of an expression by yielding
    the signal names that appear in it, without bit ranges or constant/value
    metadata.
    - discovering referenced signals during scan/connect passes
    - collecting condition or control dependencies
    - building dotted names for member accesses
    Examples:
        a + b
            -> yields: a, b

        fifo_q[cnt_q].integrity
            -> yields: fifo_q.integrity, cnt_q

        ifc.req.data
            -> yields: ifc.req.data

        cond ? x : y
            -> yields: cond, x, y
            (or only x / y if cond is constant and can be resolved)
    """
        match type(expr):
            case ast.AssignmentExpression:
                yield from self.get_short_expr(expr.right)
                yield from self.get_short_expr(expr.left)
            case ast.BinaryExpression:
                yield from self.get_short_expr(expr.left)
                yield from self.get_short_expr(expr.right)
            case ast.CallExpression:
                for argument in expr.arguments:
                    yield from self.get_short_expr(argument)
            case ast.ConcatenationExpression:
                for e in expr.operands:
                    yield from self.get_short_expr(e)
            case ast.ConditionalExpression:
                constant = expr.conditions[0].expr.constant
                if constant:
                    if int(str(constant)[-1]):
                        yield from self.get_short_expr(expr.left)
                    else:
                        yield from self.get_short_expr(expr.right)
                else:
                    yield from self.get_short_expr(expr.conditions[0].expr)
                    yield from self.get_short_expr(expr.left)
                    yield from self.get_short_expr(expr.right)
            case ast.ConversionExpression | ast.UnaryExpression:
                yield from self.get_short_expr(expr.operand)
            case ast.ElementSelectExpression:
                yield from self.get_short_expr(expr.selector)
                yield from self.get_short_expr(expr.value)
            case ast.NamedValueExpression:
                signal = self.get_name(expr.symbol)
                if not type(expr.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol]:
                    yield signal
            case ast.RangeSelectExpression:
                yield from self.get_short_expr(expr.value)
            case ast.ReplicationExpression:
                yield from self.get_short_expr(expr.concat)

            case ast.MemberAccessExpression:
                member = getattr(expr.member, "name", str(expr.member))
                any_base = False
                for base in self._get_member_owner_bases(expr.value):
                    any_base = True
                    yield f"{base}.{member}"
                #special case for struct[element].field
                yield from self._get_extra_expr_dependencies(expr.value)

                if not any_base:
                    return

            case ast.HierarchicalValueExpression:
                name = self.get_name(expr.symbol)
                root = name.split(".", 1)[0]

                # Ignore enum values / parameters same as NamedValueExpression
                if not type(expr.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol]:
                    yield name
            case ast.IntegerLiteral | ast.UnbasedUnsizedIntegerLiteral:
                # constants are not signal names so ignore
                return
            case ast.ArbitrarySymbolExpression:
                # represents a symbol-like expression that is not a plain named signal
                return
            case ast.StructuredAssignmentPatternExpression:
                for elem in expr.elements:
                    yield from self.get_short_expr(elem)
            case _:
                return

    def get_full_expr(self, expr, **kwargs) -> Iterator[str, bool, int, int]:
        """Extracts detailed dependency information from an expression.
            returns not only the signal/value
           name, but also metadata describing how it participates in the expression.

           Each yielded tuple has the form:
               (name, is_signal, start, end)

           where:
               name:
                   signal name or constant/value representation
               is_signal:
                   True if this represents a real signal dependency,
                   False for constants / parameter-like values
               start, end:
                   bit range covered by this part of the expression

           Examples:
               a + b
                   -> yields entries for a and b with their width/range metadata

               foo[3]
                   -> yields foo as the selected base expression
                      and may additionally include selector dependencies

               fifo_q[cnt_q].integrity
                   -> yields:
                      fifo_q.integrity as signal dependency
                      cnt_q as selector dependency
           """
        match type(expr):
            case ast.BinaryExpression:
                yield from self.get_full_expr(expr.left, **kwargs)
                yield from self.get_full_expr(expr.right, **kwargs)
            case ast.CallExpression:
                for e in expr.arguments:
                    yield from self.get_full_expr(e, **kwargs)
            case ast.ConcatenationExpression:
                start = kwargs.pop("start", 0)
                for e in expr.operands:
                    yield from self.get_full_expr(e, start=start, **kwargs)
                    start += e.effectiveWidth
            case ast.AssignmentExpression:
                yield from self.get_full_expr(expr.right, **kwargs)
            case ast.ConditionalExpression:
                constant = expr.conditions[0].expr.constant
                if constant:
                    if int(str(constant)[-1]):
                        yield from self.get_full_expr(expr.left, **kwargs)
                    else:
                        yield from self.get_full_expr(expr.right, **kwargs)
                else:
                    yield from self.get_full_expr(expr.conditions[0].expr, **{**kwargs, "width": expr.effectiveWidth})
                    yield from self.get_full_expr(expr.left, **kwargs)
                    yield from self.get_full_expr(expr.right, **kwargs)
            case ast.ConversionExpression | ast.UnaryExpression:
                yield from self.get_full_expr(expr.operand, **kwargs)
            case ast.ElementSelectExpression:
                left = kwargs.get("left", None)
                width = kwargs.pop("width", expr.effectiveWidth)
                if left:
                    for l_value, _, _, _ in self.get_full_expr(expr.value, width=width, **kwargs):
                        for r_value, r_constant, _, _ in self.get_full_expr(expr.selector, width=width, **kwargs):
                            if r_constant and l_value not in self.module.get_parameters().keys():
                                self.module.add_edge(r_value, l_value)
                else:
                    yield from self.get_full_expr(expr.selector, width=width, **kwargs)
                yield from self.get_full_expr(expr.value, width=width, **kwargs)
            case ast.IntegerLiteral:
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                end = start + width - 1
                yield expr.value, False, start, end
            case ast.UnbasedUnsizedIntegerLiteral:
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                end = start + width - 1
                yield expr.value, False, start, end
            case ast.ArbitrarySymbolExpression:
                #This prevents empty missing behavior without incorrectly adding graph edges from a fake signal.
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                end = start + width - 1
                yield str(expr), False, start, end
            case ast.NamedValueExpression:
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                signal = self.get_name(expr.symbol)
                end = start + width - 1
                if type(expr.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol] or str(
                        expr.type) == "int unsigned":
                    yield signal, False, start, end
                else:
                    yield signal, True, start, end
            case ast.RangeSelectExpression:
                width = kwargs.pop("width", expr.effectiveWidth)
                yield from self.get_full_expr(expr.value, width=width, **kwargs)
            case ast.ReplicationExpression:
                yield from self.get_full_expr(expr.concat, **{**kwargs, "width": expr.effectiveWidth})
            case ast.MemberAccessExpression:
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                end = start + width - 1
                member = getattr(expr.member, "name", str(expr.member))

                # Special case: struct[element].field
                if isinstance(expr.value, ast.ElementSelectExpression):
                    # Data dependency: selected aggregate field
                    for base in self.get_short_expr(expr.value.value):
                        yield f"{base}.{member}", True, start, end

                    # Selector dependency: element
                    yield from self.get_full_expr(expr.value.selector, **kwargs)
                    return

                # Default behavior
                name = next(self.get_short_expr(expr), None)
                if name is None:
                    return
                yield name, True, start, end

            case ast.HierarchicalValueExpression:
                start = kwargs.get("start", 0)
                width = kwargs.get("width", expr.effectiveWidth)
                end = start + width - 1

                name = self.get_name(expr.symbol)
                # Follow same constant policy as NamedValueExpression
                if type(expr.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol] or str(
                        expr.type) == "int unsigned":
                    yield name, False, start, end
                else:
                    yield name, True, start, end

            case ast.StructuredAssignmentPatternExpression:
                for elem in expr.elements:
                    yield from self.get_full_expr(elem, **kwargs)

            case _:
                return

    def add_dependency(self, expression, fanin):
        """Adds dependencies to the fanin set based on the given expression object."""
        fanin_mod = deepcopy(fanin)
        match type(expression):
            case ast.EventListControl:
                for e in expression.events:
                    expr = next(self.get_short_expr(e.expr))
                    self.module.set_event_trigger(expr)
                    fanin_mod.add(expr)
            case ast.SignalEventControl:
                expr = next(self.get_short_expr(expression.expr))
                self.module.set_event_trigger(expr)
                fanin_mod.add(expr)
        return fanin_mod

    def _state_target_for_lhs(self, name: str) -> str:
        """Choose which signal should be marked as state for a nonblocking LHS.

        Rule:
        - If the immediate parent is a real signal node, collapse to the
          shallowest existing signal ancestor.
        - Otherwise keep the leaf itself.
        """
        if "." not in name:
            return name

        immediate_parent = name.rsplit(".", 1)[0]
        if not self.module.has_signal(immediate_parent):
            return name

        parts = name.split(".")
        for i in range(1, len(parts)):
            prefix = ".".join(parts[:i])
            if self.module.has_signal(prefix):
                return prefix

        return name

    def assign(self, node, fanin):
        """Creates dependencies based on the given assignment node and the fanin set."""

        left = list(self.get_full_expr(node.left, left=True))
        right = list(self.get_full_expr(node.right))

        for l_value, l_constant, l_start, l_end in left:
            # immediate parent only
            l_parent = None
            if "." in l_value:
                parent = l_value.rsplit(".", 1)[0]
                if self.module.has_signal(parent):
                    l_parent = parent

            for f in fanin:
                self.module.add_edge(f, l_value)

            for r_value, r_is_signal, r_start, r_end in right:

                # immediate parent only
                if "." in r_value:
                    r_parent = r_value.rsplit(".", 1)[0]
                    if self.module.has_signal(r_parent) and self.module.has_signal(r_value):
                        self.module.add_edge(r_parent, r_value)
                        self.module.add_edge(r_value, r_parent)

                if l_start <= r_end and r_start <= l_end:
                    if r_is_signal:
                        self.module.add_edge(r_value, l_value)

            # immediate parent only
            if l_parent is not None and self.module.has_signal(l_value):
                self.module.add_edge(l_value, l_parent)

            if node.isNonBlocking and l_value in self.module.get_signals():

                state_target = self._state_target_for_lhs(l_value) or l_value

                if state_target in self.module.get_signals():
                    self.module.set_state(state_target)