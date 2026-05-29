class BaseVisitor:
    """
    Base class for all analysis visitors.

    Provides generic AST traversal and dynamic dispatch based on node
    type (visit_<NodeType>). Specific analysis passes extend this class
    and implement handlers for the nodes they care about.

    The visitors operate on the elaborated pyslang AST to perform
    different analysis stages such as declaration collection,
    signal discovery, and dependency construction.
    """

    def __init__(self, analysis: "Analysis"):
        self.a = analysis

    def visit(self, node, fanin):
        if node is None:
            return None

        if type(node) in self.a._ignored:
            return None

        func = getattr(self, f"visit_{type(node).__name__}", None)
        if func is not None:
            return func(node, fanin)

        return self.generic_visit(node, fanin)

    def generic_visit(self, node, fanin):
        # members is safe and useful for some symbol containers
        if hasattr(node, "members"):
            for m in node.members:
                if m is not None and m is not node:
                    self.visit(m, fanin)
            return

        # only traverse explicitly known child attributes
        for attr in (
                "body", "stmt", "ifTrue", "ifFalse", "expr", "symbol", "assignment",
                "value", "left", "right", "operand", "selector", "concat", "timing",
                "statement", "list", "entries", "events", "arguments", "operands"
        ):
            if not hasattr(node, attr):
                continue

            child = getattr(node, attr)
            if child is None or child is node:
                continue

            if isinstance(child, (str, int, float, bool, bytes)):
                continue

            if isinstance(child, (list, tuple)):
                for c in child:
                    if c is not None and c is not node:
                        self.visit(c, fanin)
            else:
                self.visit(child, fanin)
