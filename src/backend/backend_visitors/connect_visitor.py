from copy import deepcopy

from src.backend.backend_visitors.base_visitor import BaseVisitor


# pylint: disable=C0103
# Function naming convention disabled for Visitor classes to match token names
# pylint: disable=C0116
# Function docstrings omitted for Visitor classes for brevity
# pylint: disable=W0613
# Unused argument warning ignored for consistency of visitor functions

class ConnectVisitor(BaseVisitor):
    """Third analysis pass.
       Analyzes assignments, conditions, and timing constructs to build
       signal dependencies, edges, and module connections.
       """
    def visit_InstanceSymbol(self, node, fanin):
        instance = self.a.get_name(node)

        for child in node.body:
            self.visit(child, fanin)

        if node.portConnections:
            for connection in node.portConnections:
                dir_mapped = self.a._map_pyslang_port_dir(connection.port)
                formal_name = f"{instance}.{connection.port.name}"
                self.a.module.add_connection(
                    instance,
                    self.a.get_short_expr(connection.expression),
                    formal_name,
                    dir_mapped
                )

    def visit_NetSymbol(self, node, fanin):
        name = self.a.get_name(node)
        if node.initializer:
            for e in self.a.get_short_expr(node.initializer):
                if e is not None:
                    self.a.module.add_edge(e, name)

    def visit_VariableSymbol(self, node, fanin):
        name = self.a.get_name(node)
        if node.initializer:
            for e in self.a.get_short_expr(node.initializer):
                if e is not None:
                    self.a.module.add_edge(e, name)

    def visit_AssignmentExpression(self, node, fanin):
        self.a.assign(node, fanin)

    def visit_ConditionalStatement(self, node, fanin):
        fanin_mod = deepcopy(fanin)
        for c in node.conditions:
            for expr in set(self.a.get_short_expr(c.expr)):
                if expr is None:
                    continue
                self.a.module.set_condition(expr)
                fanin_mod.add(expr)

        self.visit(node.ifTrue, fanin_mod)
        if node.ifFalse:
            self.visit(node.ifFalse, fanin_mod)

    def visit_UnaryExpression(self, node, fanin):
        op_str = str(getattr(node, "op", "")).lower()

        if "increment" in op_str or "decrement" in op_str:
            for expr in set(self.a.get_short_expr(node.operand)):
                if expr is None:
                    continue

                for f in fanin:
                    self.a.module.add_edge(f, expr)

    def visit_CaseStatement(self, node, fanin):
        fanin_mod = deepcopy(fanin)
        fanin_mod.update(set(self.a.get_short_expr(node.expr)))
        for c in node.items:
            self.visit(c.stmt, fanin_mod)

    def visit_TimedStatement(self, node, fanin):
        fanin_mod = self.a.add_dependency(node.timing, fanin)
        self.visit(node.stmt, fanin_mod)

    def visit_ContinuousAssignSymbol(self, node, fanin):
        self.visit(node.assignment, fanin)

    def visit_ForLoopStatement(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_ProceduralBlockSymbol(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_BlockStatement(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_StatementList(self, node, fanin):
        for child in node.list:
            self.visit(child, fanin)

    def visit_ExpressionStatement(self, node, fanin):
        self.visit(node.expr, fanin)

    def visit_VariableDeclStatement(self, node, fanin):
        self.visit(node.symbol, fanin)

    def visit_GenerateBlockSymbol(self, node, fanin):
        if not node.isUninstantiated:
            for child in node:
                self.visit(child, fanin)

    def visit_GenerateBlockArraySymbol(self, node, fanin):
        if not node.isUninstantiated:
            for entry in node.entries:
                self.visit(entry, fanin)
