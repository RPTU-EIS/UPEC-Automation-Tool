import pyslang.ast as ast

from src.backend.backend_visitors.base_visitor import BaseVisitor


# pylint: disable=C0103
# Function naming convention disabled for Visitor classes to match token names
# pylint: disable=C0116
# Function docstrings omitted for Visitor classes for brevity
# pylint: disable=W0613
# Unused argument warning ignored for consistency of visitor functions


class ScanVisitor(BaseVisitor):
    """
    Second analysis pass.

    Traverses expressions to discover additional signal references
    (e.g., hierarchical or member accesses) that were not declared
    explicitly in the first pass.
    """
    # -------------------------
    # Structural / statement nodes
    # -------------------------
    def visit_InstanceSymbol(self, node, fanin):

        for child in node.body:
            self.visit(child, fanin)

        if node.portConnections:
            for connection in node.portConnections:
                self.visit(connection.expression, fanin)

    def visit_NetSymbol(self, node, fanin):
        if node.initializer:
            self.visit(node.initializer, fanin)

    def visit_VariableSymbol(self, node, fanin):
        if node.initializer:
            self.visit(node.initializer, fanin)

    def visit_ConditionalStatement(self, node, fanin):
        for c in node.conditions:
            self.visit(c.expr, fanin)

        self.visit(node.ifTrue, fanin)
        if node.ifFalse:
            self.visit(node.ifFalse, fanin)

    def visit_CaseStatement(self, node, fanin):
        self.visit(node.expr, fanin)
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
        self.visit(node.timing, fanin)
        self.visit(node.stmt, fanin)

    def visit_StatementList(self, node, fanin):
        for child in node.list:
            self.visit(child, fanin)

    def visit_ExpressionStatement(self, node, fanin):
        self.visit(node.expr, fanin)

    def visit_VariableDeclStatement(self, node, fanin):
        self.visit(node.symbol, fanin)

    def visit_AssignmentExpression(self, node, fanin):
        self.visit(node.left, fanin)
        self.visit(node.right, fanin)

    # -------------------------
    # Timing / event nodes
    # -------------------------

    def visit_EventListControl(self, node, fanin):
        for e in node.events:
            self.visit(e.expr, fanin)

    def visit_SignalEventControl(self, node, fanin):
        self.visit(node.expr, fanin)

    def visit_EventControlWithExpression(self, node, fanin):
        self.visit(node.expr, fanin)

    # -------------------------
    # Expression wrapper nodes
    # -------------------------

    def visit_ElementSelectExpression(self, node, fanin):
        self.visit(node.value, fanin)
        self.visit(node.selector, fanin)

    def visit_RangeSelectExpression(self, node, fanin):
        self.visit(node.value, fanin)

    def visit_BinaryExpression(self, node, fanin):
        self.visit(node.left, fanin)
        self.visit(node.right, fanin)

    def visit_UnaryExpression(self, node, fanin):
        self.visit(node.operand, fanin)

    def visit_ConversionExpression(self, node, fanin):
        self.visit(node.operand, fanin)

    def visit_ConditionalExpression(self, node, fanin):
        for c in node.conditions:
            self.visit(c.expr, fanin)
        self.visit(node.left, fanin)
        self.visit(node.right, fanin)

    def visit_ConcatenationExpression(self, node, fanin):
        for op in node.operands:
            self.visit(op, fanin)

    def visit_CallExpression(self, node, fanin):
        for arg in node.arguments:
            self.visit(arg, fanin)

    def visit_ReplicationExpression(self, node, fanin):
        self.visit(node.concat, fanin)

    def visit_StructuredAssignmentPatternExpression(self, node, fanin):
        for elem in node.elements:
            self.visit(elem, fanin)

    def visit_EmptyArgumentExpression(self, node, fanin):
        return
    # -------------------------
    # Leaf-ish expression nodes that may add discovered signals
    # These are the important ones that actually discover names.
    # -------------------------

    def visit_NamedValueExpression(self, node, fanin):

        """Represents a plain named signal reference.
            Example syntax:
            a
            cpuif_req
            decoded_reg_strb.SHA256_CTRL
            may reveal dotted names that were not explicitly declared"""

        if type(node.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol]:
            return

        name = self.a.get_name(node.symbol)
        root = name.split(".", 1)[0]

        # Only create bundle root for dotted names that are not true instance hierarchy
        if "." in name and not self.a.module.has_signal(root) and not self.a.module.has_instance(root):
            self.a.module.add_signal(root, "bundle_root", 0)

        width = getattr(getattr(node, "type", None), "bitWidth", 1)
        typ = str(getattr(node, "type", "named"))

        # Plain names should already be declared; only add dotted discovered names here
        if "." in name and not self.a.module.has_signal(name):
            self.a.module.add_signal(name, typ, width)

    def visit_MemberAccessExpression(self, node, fanin):
        """Represents a.b style access.
            Example syntax:
            ifc.valid
            ifc.req.data
            decoded_reg_strb.SHA256_CTRL
            a.b.c
            this is one of the main ways interface / struct member signals appear"""


        names = list(self.a.get_short_expr(node))

        for name in names:

            root = name.split(".", 1)[0]

            # keep this ONLY for synthetic roots (optional)
            if "." in name and not self.a.module.has_signal(root) and not self.a.module.has_instance(root):
                self.a.module.add_signal(root, "bundle_root", 0)

            width = getattr(getattr(node, "type", None), "bitWidth", 1)
            typ = str(getattr(node, "type", "member"))

            if "." in name and not self.a.module.has_signal(name):
                self.a.module.add_signal(name, typ, width)
            parent = name.rsplit(".", 1)[0]
            if self.a.module.has_signal(parent):
                self.a.module.add_edge(parent, name)
                self.a.module.add_edge(name, parent)
        self.visit(node.value, fanin)

    def visit_HierarchicalValueExpression(self, node, fanin):
        """Represents a resolved hierarchical/symbolic reference.
            Example syntax:
            top.u1.sig
            hwif_in.reset_b
            used to discover hierarchical/member-like names"""

        name = self.a.get_name(node.symbol)
        root = name.split(".", 1)[0]

        # discovering missing interface related names
        # adding the interface as an instance and also as a signal/bundle root
        if "." in name and not self.a.module.has_signal(root) and not self.a.module.has_instance(root):
            self.a.module.add_signal(root, "bundle_root", 0)

        if type(node.symbol) in [ast.EnumValueSymbol, ast.ParameterSymbol]:
            return

        width = getattr(getattr(node, "type", None), "bitWidth", 1)
        typ = str(getattr(node, "type", "hier"))

        if "." in name and not self.a.module.has_signal(name):
            self.a.module.add_signal(name, typ, width)
        parent = name.rsplit(".", 1)[0]
        if self.a.module.has_signal(parent):
            self.a.module.add_edge(parent, name)
            self.a.module.add_edge(name, parent)
