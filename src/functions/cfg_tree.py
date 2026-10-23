"""Parse tree node shared by the LL(1) and SLR(1) parsers and the SDD evaluator."""


class Node:
    """symbol, production index into Grammar.prods (None for terminals), children, attributes."""

    def __init__(self, symbol):
        self.symbol = symbol
        self.prod = None
        self.children = []
        self.attrs = {}
        self.id = None


def number_nodes(root):
    """Pre-order numbering; returns the nodes in that order."""
    nodes = []
    stack = [root]
    while stack:
        n = stack.pop()
        n.id = len(nodes)
        nodes.append(n)
        stack.extend(reversed(n.children))
    return nodes


def tree_to_dict(root):
    """Nested dict (iterative, safe for deep trees)."""
    number_nodes(root)
    out = {}
    stack = [(root, out)]
    while stack:
        n, d = stack.pop()
        d.update({"id": n.id, "symbol": n.symbol, "prod": n.prod, "attrs": dict(n.attrs), "children": []})
        for c in n.children:
            cd = {}
            d["children"].append(cd)
            stack.append((c, cd))
    return out
