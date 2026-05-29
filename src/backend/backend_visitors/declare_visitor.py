from src.backend.backend_visitors.base_visitor import BaseVisitor


# pylint: disable=C0103
# Function naming convention disabled for Visitor classes to match token names
# pylint: disable=C0116
# Function docstrings omitted for Visitor classes for brevity
# pylint: disable=W0613
# Unused argument warning ignored for consistency of visitor functions


class DeclareVisitor(BaseVisitor):
    """
    First analysis pass.
    Collects all explicitly declared design objects (instances, ports,
    parameters, nets, and variables) and registers them in the module model.
    """

    def visit_InstanceSymbol(self, node, fanin):
        instance = self.a.get_name(node)

        if node.portConnections:
            self.a.module.add_instantiation(
                self.a.get_name(node.definition),
                instance
            )

        for child in node.body:
            self.visit(child, fanin)

    def visit_ParameterSymbol(self, node, fanin):
        self.a.module.add_parameter(
            self.a.get_name(node),
            str(node.type),
            str(node.value),
            node.isOverridden
        )

    def visit_PortSymbol(self, node, fanin):
        dir_mapped = self.a._map_pyslang_port_dir(node)
        self.a.module.add_port(
            self.a.get_name(node),
            str(node.type),
            dir_mapped,
            node.type.bitWidth
        )

    def visit_NetSymbol(self, node, fanin):
        self.a.module.add_signal(
            self.a.get_name(node),
            str(node.type),
            node.type.bitWidth
        )

    def visit_VariableSymbol(self, node, fanin):
        self.a.module.add_signal(
            self.a.get_name(node),
            str(node.type),
            node.type.bitWidth
        )

    def visit_ConditionalStatement(self, node, fanin):
        self.visit(node.ifTrue, fanin)
        if node.ifFalse:
            self.visit(node.ifFalse, fanin)

    def visit_CaseStatement(self, node, fanin):
        for c in node.items:
            self.visit(c.stmt, fanin)

    def visit_GenerateBlockSymbol(self, node, fanin):
        if not node.isUninstantiated:
            for child in node:
                self.visit(child, fanin)

    def visit_GenerateBlockArraySymbol(self, node, fanin):
        if not node.isUninstantiated:
            for entry in node.entries:
                self.visit(entry, fanin)

    def visit_ForLoopStatement(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_ProceduralBlockSymbol(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_BlockStatement(self, node, fanin):
        self.visit(node.body, fanin)

    def visit_ContinuousAssignSymbol(self, node, fanin):
        self.visit(node.assignment, fanin)

    def visit_TimedStatement(self, node, fanin):
        self.visit(node.stmt, fanin)

    def visit_StatementList(self, node, fanin):
        for child in node.list:
            self.visit(child, fanin)

    def visit_ExpressionStatement(self, node, fanin):
        self.visit(node.expr, fanin)

    def visit_VariableDeclStatement(self, node, fanin):
        self.visit(node.symbol, fanin)
