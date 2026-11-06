"""The input/output protocol of Section 2.2 of the assignment (Items 1-2), written once and used twice:
cli/main.py runs it on stdin/stdout and POST /grammar/report runs it on the request body, so the endpoint
answers exactly what the program prints. Reading and writing are passed in as functions; no Flask here."""
from functions.cfg_grammar import Grammar, GrammarError, parse_grammar, sets_lines

MESSAGES = {
    1: "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):",
    2: "Grammar is LL(1).",
    3: "Grammar is SLR(1).",
    4: "Grammar is neither LL(1) nor SLR(1).",
}


def verdict(ll, slr):
    """Section 2.2.2: (case 1-4, message, parsers that may be used)."""
    if ll.is_ll1 and slr.is_slr1:
        return 1, MESSAGES[1], ["ll1", "slr1"]
    if ll.is_ll1:
        return 2, MESSAGES[2], ["ll1"]
    if slr.is_slr1:
        return 3, MESSAGES[3], ["slr1"]
    return 4, MESSAGES[4], []


def line_reader(readline):
    """Wraps a readline function (sys.stdin.readline, io.StringIO(text).readline): each call returns the next
    line without its line break, or None at the end of the input."""
    def read():
        line = readline()
        return None if line == "" else line.rstrip("\r\n")
    return read


def read_grammar(read_line):
    """The grammar part of the input: a line with n, then n production lines."""
    first = read_line()
    try:
        n = int(first)
    except (TypeError, ValueError):
        raise GrammarError(f"The first line must be the number of nonterminals, got {first!r}", 1) from None
    if not 0 < n <= Grammar.MAX_NONTERMINALS:     # checked before reading n lines
        raise GrammarError(f"The number of nonterminals must be between 1 and {Grammar.MAX_NONTERMINALS}.", 1)
    return parse_grammar(str(n) + "\n" + "\n".join(read_line() or "" for _ in range(n)))


def table_lines(ll, slr):
    """The lines printed by --tables: LL(1) table, LR(0) item sets and SLR(1) ACTION/GOTO."""
    out = ["LL(1) table (Algorithm 4.31):", *ll.table_lines(), "LR(0) item sets and SLR(1) ACTION/GOTO:"]
    for s, item_set in enumerate(slr.states):
        out.append(f"I{s}: " + " | ".join(slr.item_str(p, d) for p, d in sorted(item_set)))
    for (s, a), cell in sorted(slr.action.items()):
        out.append(f"ACTION[{s},{a}] = " + " / ".join(slr._act_str(c) for c in cell))
    for (s, A), t in sorted(slr.goto.items()):
        out.append(f"GOTO[{s},{A}] = {t}")
    return out


def trace_lines(trace, parser):
    """The lines printed by --trace for one string: stack, remaining input and action of every step."""
    out = []
    for st in trace:
        stack = (" ".join(st["stack"]) if parser == "ll1"
                 else " ".join((e["symbol"] or "") + str(e["state"]) for e in st["stack"]))
        out.append(f"{stack:<34} {st['input']:<16} {st['action']}")
    return out


def run_strings(p, parser, read_line, write, trace=False):
    """Reads strings until an empty line (or the end of the input); writes yes/no for each one."""
    while True:
        line = read_line()
        if line is None or line.strip() == "":
            return
        w = "" if line.strip() == "e" else line.strip()
        res = p.parse(w, trace=trace)
        if trace:
            for t in trace_lines(res["trace"], parser):
                write(t)
        write("yes" if res["accepted"] else "no")


def run_session(g, ll, slr, read_line, write, sets=False, tables=False, trace=False):
    """Everything after the grammar has been read: --sets / --tables output, the decision of Section 2.2.2 and
    the strings (in case 1 the parser is asked for until Q or the end of the input)."""
    if sets:
        for line in sets_lines(g):
            write(line)
    if tables:
        for line in table_lines(ll, slr):
            write(line)
    case, message, _ = verdict(ll, slr)
    if case == 1:
        while True:
            write(message)
            line = read_line()
            if line is None or line.strip().upper() == "Q":
                break
            choice = line.strip().upper()
            if choice == "T":
                run_strings(ll, "ll1", read_line, write, trace)
            elif choice == "B":
                run_strings(slr, "slr1", read_line, write, trace)
        return
    write(message)
    if case == 2:
        run_strings(ll, "ll1", read_line, write, trace)
    elif case == 3:
        run_strings(slr, "slr1", read_line, write, trace)
