"""LaTeX export: turns the results the server computes into a compilable .tex file with the tables the
report asks for (Section 4.1). Only standard packages: booktabs, graphicx, amsmath, longtable."""
from functions.cfg_grammar import EPS, END, is_nt, prod_str
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=2.2cm]{geometry}
\usepackage{booktabs,graphicx,amsmath,longtable}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\begin{document}
"""
_ESC = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}"}


def esc(text):
    """Escapes plain text for LaTeX."""
    return "".join(_ESC.get(c, c) for c in str(text))


def tt(text):
    """Monospaced, escaped; an empty string stays empty."""
    return r"\texttt{" + esc(text) + "}" if str(text) != "" else ""


def prod_tex(head, body):
    rhs = tt("".join(body)) if body else r"$\varepsilon$"
    return f"{esc(head)} $\\to$ {rhs}"


def prod_math(text):
    """'A -> aB' -> LaTeX."""
    head, rhs = text.split(" -> ", 1)
    return f"{esc(head)} $\\to$ " + (r"$\varepsilon$" if rhs in ("e", "") else tt(rhs))


def set_tex(items):
    parts = []
    for x in items:
        parts.append(r"$\varepsilon$" if x == EPS else (r"\texttt{\$}" if x == END else tt(x)))
    return r"$\{$" + ", ".join(parts) + r"$\}$"


def _table(caption, colspec, head, rows, label, resize=False):
    body = " \\\\\n".join(" & ".join(r) for r in rows)
    tab = (f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n{' & '.join(head)} \\\\\n\\midrule\n{body} \\\\\n\\bottomrule\n\\end{{tabular}}")
    if resize:
        tab = "\\resizebox{\\ifdim\\width>\\textwidth\\textwidth\\else\\width\\fi}{!}{%\n" + tab + "}"
    return f"\\begin{{table}}[h]\n\\centering\\small\n{tab}\n\\caption{{{caption}}}\\label{{{label}}}\n\\end{{table}}\n"


def grammar_report(g, strings=(), parser="auto", title="Grammar analysis"):
    ll, slr = LL1(g), SLR1(g)
    out = [PREAMBLE, f"\\section*{{{esc(title)}}}\n"]
    out.append("\\subsection*{Grammar}\n\\begin{tabular}{rl}\n" +
               " \\\\\n".join(f"{i} & {prod_tex(h, b)}" for i, (h, b) in enumerate(g.prods)) + "\n\\end{tabular}\n")
    # FIRST / FOLLOW (Section 4.4.2)
    from functions.cfg_grammar import sets_json
    sj = sets_json(g)
    out.append("\\subsection*{FIRST and FOLLOW}\n" + _table(
        "FIRST and FOLLOW sets (Section 4.4.2).", "lll", ["Nonterminal", "FIRST", "FOLLOW"],
        [[esc(A), set_tex(sj["first"][A]), set_tex(sj["follow"][A])] for A in g.nonterminals], "tab:sets"))
    # LL(1) (Section 4.4.3, Algorithm 4.31)
    verdict = "is" if ll.is_ll1 else r"is \textbf{not}"
    out.append("\\subsection*{LL(1)}\nThe grammar " + verdict + " LL(1) (condition of Section 4.4.3).\n")
    if ll.violations:
        out.append("\\begin{itemize}\n" + "\n".join(f"\\item {esc(v['message'])} (condition {v['condition']})." for v in ll.violations)
                   + "\n\\end{itemize}\n")
    cols = g.terminals + [END]
    rows = []
    for A in g.nonterminals:
        row = [esc(A)]
        for a in cols:
            cell = ll.table.get((A, a), [])
            row.append("; ".join(prod_math(prod_str(*g.prods[i])) for i in cell))
        rows.append(row)
    out.append(_table("Predictive parsing table $M$ (Algorithm 4.31). Several entries in a cell mean the table is multiply defined.",
                      "l" + "l" * len(cols), ["$M$"] + [r"\texttt{\$}" if a == END else tt(a) for a in cols], rows, "tab:ll1", True))
    # SLR(1) (Sections 4.6.2 - 4.6.4)
    verdict = "is" if slr.is_slr1 else r"is \textbf{not}"
    out.append("\\subsection*{SLR(1)}\nThe grammar " + verdict + f" SLR(1); the canonical collection has {len(slr.states)} LR(0) item sets.\n")
    if slr.conflicts:
        out.append("\\begin{itemize}\n" + "\n".join(
            f"\\item State {c['state']} on {tt(c['symbol'])}: {esc(c['type'])} conflict." for c in slr.conflicts) + "\n\\end{itemize}\n")
    rows = []
    for s, I in enumerate(slr.states):
        items = " \\\\ ".join(f"{esc(slr.item_str(p, d).split(' -> ')[0])} $\\to$ {tt(slr.item_str(p, d).split(' -> ')[1])}"
                             for p, d in sorted(I))
        rows.append([f"$I_{{{s}}}$", f"\\begin{{tabular}}[t]{{@{{}}l@{{}}}} {items} \\end{{tabular}}"])
    out.append("\\begin{longtable}{lp{0.8\\textwidth}}\n\\toprule\nState & Items \\\\\n\\midrule\n\\endhead\n" +
               " \\\\\n".join(" & ".join(r) for r in rows) + " \\\\\n\\bottomrule\n\\caption{LR(0) item sets (Section 4.6.2).}\n\\end{longtable}\n")
    t = slr.table_json()
    head = ["State"] + [r"\texttt{\$}" if a == END else tt(a) for a in t["terminals"]] + [esc(A) for A in t["nonterminals"]]
    def act(a):
        a = a.replace("shift ", "s").replace("accept", "acc")
        if a.startswith("reduce "):
            return "r " + prod_math(a[7:])
        return esc(a)
    rows = []
    for r in t["rows"]:
        rows.append([str(r["state"])] + [" / ".join(act(x) for x in r["action"].get(a, [])) for a in t["terminals"]]
                    + [str(r["goto"].get(A, "")) for A in t["nonterminals"]])
    out.append(_table("SLR(1) ACTION and GOTO tables (Section 4.6.4).", "l" + "l" * (len(head) - 1), head, rows, "tab:slr", True))
    # parsing traces
    use = parser if parser != "auto" else ("ll1" if ll.is_ll1 else "slr1" if slr.is_slr1 else None)
    if strings and use:
        p = ll if use == "ll1" else slr
        out.append(f"\\subsection*{{Parsing steps ({'LL(1), Algorithm 4.34' if use == 'll1' else 'SLR(1), Section 4.6.3'})}}\n")
        for k, s in enumerate(strings):
            w = "" if s.strip() == "e" else s.strip()
            r = p.parse(w, trace=True)
            rows = []
            for st in r["trace"]:
                stack = (" ".join(st["stack"]) if use == "ll1" else
                         " ".join((e["symbol"] or "") + str(e["state"]) for e in st["stack"]))
                rows.append([tt(stack or "-") if use == "ll1" else tt(stack), tt(st["input"]),
                             prod_math(st["action"][7:]) if st["action"].startswith("output ") else
                             (esc(st["action"][:7]) + prod_math(st["action"][7:]) if st["action"].startswith("reduce ") else esc(st["action"]))])
            shown = esc(w) or r"$\varepsilon$"
            out.append(_table(f"Input \\texttt{{{shown}}}: " + ("accepted" if r["accepted"] else "rejected") + ".",
                              "lll", ["Stack", "Input", "Action"], rows, f"tab:trace{k}"))
    out.append("\\end{document}\n")
    return "\n".join(out)


def sdd_report(sdd, result, title="Syntax-directed definition"):
    d = sdd.describe()
    c = d["classification"]
    out = [PREAMBLE, f"\\section*{{{esc(title)}}}\n", f"\\textbf{{{esc(d['name'])}}}. {esc(d['description'])}\n"]
    out.append("\\subsection*{Grammar}\n\\begin{tabular}{l}\n" + " \\\\\n".join(prod_math(p) for p in d["grammar"]) + "\n\\end{tabular}\n")
    out.append("\\subsection*{Attributes}\n" + _table("Attribute table.", "lll", ["Symbol", "Attribute", "Kind"],
               [[esc(a["symbol"]), tt(a["attribute"]), esc(a["kind"])] for a in d["attributes"]], "tab:attrs"))
    rows = [[prod_math(r["production"]), "\\begin{tabular}[t]{@{}l@{}}" + " \\\\ ".join(tt(x) for x in r["rules"]) + "\\end{tabular}"]
            for r in d["rules"]]
    out.append("\\subsection*{Semantic rules}\n" + _table("Semantic rules (format of Fig. 5.1).", "lp{0.65\\textwidth}",
               ["Production", "Semantic rules"], rows, "tab:rules"))
    out.append(f"\\subsection*{{Classification}}\nThe SDD is \\textbf{{{esc(c['verdict'])}}}.\n")
    if c["reasons"]:
        out.append("\\begin{itemize}\n" + "\n".join(f"\\item {esc(r)}" for r in c["reasons"]) + "\n\\end{itemize}\n")
    if result:
        w = result["input"]
        out.append(f"\\subsection*{{Evaluation of \\texttt{{{esc(w)}}}}}\n")
        if not result["accepted"]:
            out.append("The string is not in the language of the grammar.\n")
        elif result.get("circular"):
            out.append("The SDD is \\textbf{circular}. Cycle: " + esc("  ->  ".join(result["cycle"])) + ".\n")
        else:
            out.append(f"Main attribute {esc(d['main'])} $=$ \\texttt{{{esc(result['main']['value'])}}}.\n")
            lines, stack = [], [(result["tree"], 0)]
            while stack:
                n, depth = stack.pop()
                at = ", ".join(f"{k}={v}" for k, v in n["attrs"].items())
                lines.append("  " * depth + f"{n['symbol']}#{n['id']}" + (f" [{at}]" if at else ""))
                for ch in reversed(n["children"]):
                    stack.append((ch, depth + 1))
            out.append("\\paragraph{Annotated parse tree}\n\\begin{small}\\begin{verbatim}\n" + "\n".join(lines[:200]) + "\n\\end{verbatim}\\end{small}\n")
            rows = [[str(s["step"]), tt(s["vertex"]), tt(s["rule"]), tt(s["value"])] for s in result["order"][:120]]
            out.append(_table("Evaluation order (a topological order of the dependency graph).", "rlll", ["\\#", "Attribute", "Rule", "Value"],
                              rows, "tab:order"))
    out.append("\\end{document}\n")
    return "\n".join(out)
