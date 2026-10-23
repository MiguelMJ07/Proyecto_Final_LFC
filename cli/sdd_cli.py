"""Item 3 from the command line (Section 3 of the assignment, Step 5).

    python cli/sdd_cli.py [--preset luhn|weighted] [--circular] [--graph] < strings

Strings are read one per line until an empty line. For each one prints `no`, or the annotated parse tree
(one node per line, indented by depth), the evaluation order and the value of the main attribute.
With --circular the SDD is temporarily made circular (Step 6) and the cycle is reported."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from functions.cfg_sdd import SDD, SDDError, evaluate, with_circular_variant   # noqa: E402
from functions.cfg_sdd_presets import PRESETS                                  # noqa: E402


def print_tree(node, depth=0):
    stack = [(node, depth)]
    while stack:
        n, d = stack.pop()
        attrs = ", ".join(f"{k}={v}" for k, v in n["attrs"].items())
        print(f"{'  ' * d}{n['symbol']}#{n['id']}" + (f" [{attrs}]" if attrs else ""))
        for c in reversed(n["children"]):
            stack.append((c, d + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="luhn", choices=sorted(PRESETS))
    ap.add_argument("--circular", action="store_true")
    ap.add_argument("--graph", action="store_true")
    args = ap.parse_args()
    defn = PRESETS[args.preset]
    if args.circular:
        defn = with_circular_variant(defn)
    try:
        sdd = SDD(defn)
    except SDDError as e:
        print(f"Invalid SDD: {e}")
        return 1
    for line in sys.stdin:
        w = line.strip()
        if w == "":
            break
        w = "" if w == "e" else w
        try:
            r = evaluate(sdd, w)
        except SDDError as e:
            print(f"Error: {e}")
            return 1
        if not r["accepted"]:
            print("no")
            continue
        if args.graph:
            print("Dependency graph (used -> defined):")
            for e in r["edges"]:
                print(f"  {e['from']} -> {e['to']}")
        if r["circular"]:
            print("The SDD is circular. Cycle found:")
            print("  " + " -> ".join(r["cycle"]))
            return 0
        print("Annotated parse tree:")
        print_tree(r["tree"])
        print("Evaluation order:")
        print("  " + ", ".join(s["vertex"] for s in r["order"]))
        print(f"Main attribute {r['main']['attribute']} = {r['main']['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
