"""Items 1 and 2 from the command line, with the input/output protocol of Section 2.2 of the assignment.

    python cli/main.py [--sets] [--tables] [--trace] < input

--sets    print FIRST and FOLLOW after reading the grammar (required by the assignment)
--tables  also print the LL(1) table and the LR(0) automaton with the SLR(1) tables (extra)
--trace   print every parsing step (extra, handy for the report)
The same functions serve the web server (src/functions)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from functions.cfg_grammar import GrammarError, parse_grammar, sets_lines   # noqa: E402
from functions.cfg_ll1 import LL1                                           # noqa: E402
from functions.cfg_slr1 import SLR1                                         # noqa: E402


def read_line():
    line = sys.stdin.readline()
    return None if line == "" else line.rstrip("\r\n")


def run_strings(parser, kind, trace_on):
    """Reads strings until an empty line; prints yes/no for each one."""
    while True:
        line = read_line()
        if line is None or line.strip() == "":
            return
        w = "" if line.strip() == "e" else line.strip()
        res = parser.parse(w, trace=trace_on)
        if trace_on:
            for st in res["trace"]:
                stack = (" ".join(st["stack"]) if kind == "ll1"
                         else " ".join((e["symbol"] or "") + str(e["state"]) for e in st["stack"]))
                print(f"{stack:<34} {st['input']:<16} {st['action']}")
        print("yes" if res["accepted"] else "no")
        sys.stdout.flush()


def main():
    args = sys.argv[1:]
    try:
        n = int(read_line())
        g = parse_grammar(str(n) + "\n" + "\n".join(read_line() or "" for _ in range(n)))
    except (ValueError, TypeError) as e:           # GrammarError is a ValueError
        print(f"Invalid grammar: {e}")
        return 1
    if "--sets" in args:
        print("\n".join(sets_lines(g)))
    ll, slr = LL1(g), SLR1(g)
    if "--tables" in args:
        print("LL(1) table (Algorithm 4.31):")
        print("\n".join(ll.table_lines()))
        print("LR(0) item sets and SLR(1) ACTION/GOTO:")
        for s, item_set in enumerate(slr.states):
            print(f"I{s}: " + " | ".join(slr.item_str(p, d) for p, d in sorted(item_set)))
        for (s, a), cell in sorted(slr.action.items()):
            print(f"ACTION[{s},{a}] = " + " / ".join(slr._act_str(c) for c in cell))
        for (s, A), t in sorted(slr.goto.items()):
            print(f"GOTO[{s},{A}] = {t}")
    trace_on = "--trace" in args
    if ll.is_ll1 and slr.is_slr1:
        while True:
            print("Select a parser (T: for LL(1), B: for SLR(1), Q: quit):")
            sys.stdout.flush()
            line = read_line()
            if line is None or line.strip().upper() == "Q":
                break
            choice = line.strip().upper()
            if choice == "T":
                run_strings(ll, "ll1", trace_on)
            elif choice == "B":
                run_strings(slr, "slr1", trace_on)
    elif ll.is_ll1:
        print("Grammar is LL(1).")
        sys.stdout.flush()
        run_strings(ll, "ll1", trace_on)
    elif slr.is_slr1:
        print("Grammar is SLR(1).")
        sys.stdout.flush()
        run_strings(slr, "slr1", trace_on)
    else:
        print("Grammar is neither LL(1) nor SLR(1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
