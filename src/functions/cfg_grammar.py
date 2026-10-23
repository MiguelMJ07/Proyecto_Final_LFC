"""CFG layer: grammar reading, FIRST and FOLLOW.

Book: Aho et al., Compilers (2nd ed.), Section 4.4.2 (FIRST and FOLLOW) and the
literal LL(1) condition of Section 4.4.3. No Flask / HTTP code here.
"""

EPS = "e"    # epsilon, as in Section 2.2 of the assignment
END = "$"    # end marker


class GrammarError(ValueError):
    """Invalid grammar text. `line` is the 1-based input line when known."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.line = line


def is_nt(symbol):
    """Nonterminals are upper-case letters (Section 2.2)."""
    return symbol.isupper()


def prod_str(head, body):
    return f"{head} -> {''.join(body) if body else EPS}"


class Grammar:
    """A context-free grammar. `prods` is a list of (head, body-tuple);
    an empty body is an epsilon production."""

    MAX_NONTERMINALS = 26
    MAX_PRODUCTIONS = 400

    def __init__(self, lines):
        self.prods = []
        self.start = "S"
        heads = []
        for ln, line in enumerate(lines, start=2):   # line 1 is n
            if "->" not in line:
                raise GrammarError(f"Missing '->' in production line: {line!r}", ln)
            head, rhs = line.split("->", 1)
            head = head.strip()
            if len(head) != 1 or not head.isupper():
                raise GrammarError(f"Left side must be a single capital letter, got {head!r}", ln)
            if head in heads:
                raise GrammarError(f"Nonterminal {head} appears on the left side of more than one line", ln)
            heads.append(head)
            alts = rhs.split()
            if not alts:
                raise GrammarError(f"Nonterminal {head} has no derivation alternatives", ln)
            for alt in alts:
                if alt == EPS:
                    self.prods.append((head, ()))
                    continue
                for ch in alt:
                    if ch == EPS or ch == END:
                        raise GrammarError(
                            f"Symbol {ch!r} is reserved ('e' is epsilon, '$' is the end marker) "
                            f"and cannot be used inside alternative {alt!r}", ln)
                self.prods.append((head, tuple(alt)))
        if len(self.prods) > self.MAX_PRODUCTIONS:
            raise GrammarError(f"Too many productions (limit {self.MAX_PRODUCTIONS}).")
        if "S" not in heads:
            raise GrammarError("The start symbol S has no production")
        used = {x for _, b in self.prods for x in b if is_nt(x)}
        missing = sorted(used - set(heads))
        if missing:
            raise GrammarError(f"Nonterminal(s) {', '.join(missing)} used but never defined on a left side")
        self.nonterminals = sorted(heads)
        self.terminals = sorted({x for _, b in self.prods for x in b if not is_nt(x)})
        self.first_events = []
        self.follow_events = []
        self.first = self._compute_first()
        self.follow = self._compute_follow()

    # ----------------------------------------------------------------- FIRST
    def first_of(self, symbols, first=None):
        """FIRST of a string X1 X2 ... Xn (Section 4.4.2). May contain EPS."""
        first = self.first if first is None else first
        res = set()
        for X in symbols:
            if not is_nt(X):                     # rule 1: FIRST(a) = {a}
                res.add(X)
                return res
            res |= first[X] - {EPS}
            if EPS not in first[X]:
                return res
        res.add(EPS)                             # every Xi (or the empty string) derives epsilon
        return res

    def nullable(self, symbols):
        return EPS in self.first_of(symbols)

    def _compute_first(self):
        first = {A: set() for A in self.nonterminals}
        changed, rnd = True, 0
        while changed:                           # apply the rules until nothing changes
            changed, rnd = False, rnd + 1
            for idx, (A, body) in enumerate(self.prods):
                s = self.first_of(body, first)
                new = s - first[A]
                if new:
                    first[A] |= new
                    changed = True
                    rule = 3 if not body else 2
                    self.first_events.append({"round": rnd, "symbol": A, "added": sorted(new),
                                              "rule": rule, "production": prod_str(A, body)})
        return first

    # ---------------------------------------------------------------- FOLLOW
    def _compute_follow(self):
        follow = {A: set() for A in self.nonterminals}
        follow[self.start].add(END)              # rule 1
        self.follow_events.append({"round": 0, "symbol": self.start, "added": [END],
                                   "rule": 1, "production": None})
        changed, rnd = True, 0
        while changed:
            changed, rnd = False, rnd + 1
            for A, body in self.prods:
                for i, B in enumerate(body):
                    if not is_nt(B):
                        continue
                    fb = self.first_of(body[i + 1:])
                    adds = [(fb - {EPS}, 2)]                       # rule 2
                    if EPS in fb:
                        adds.append((follow[A], 3))                # rule 3
                    for s, rule in adds:
                        new = set(s) - follow[B]
                        if new:
                            follow[B] |= new
                            changed = True
                            self.follow_events.append({"round": rnd, "symbol": B, "added": sorted(new),
                                                       "rule": rule, "production": prod_str(A, body)})
        return follow

    # ------------------------------------------------------------- utilities
    def left_recursive(self):
        """Nonterminals A with A =>+ A alpha (direct or indirect). Diagnostic only."""
        reach = {A: set() for A in self.nonterminals}
        for A, body in self.prods:
            for X in body:
                if is_nt(X):
                    reach[A].add(X)
                if not (is_nt(X) and EPS in self.first[X]):
                    break
        changed = True
        while changed:
            changed = False
            for A in self.nonterminals:
                extra = set().union(*(reach[B] for B in reach[A])) - reach[A] if reach[A] else set()
                if extra:
                    reach[A] |= extra
                    changed = True
        return [A for A in self.nonterminals if A in reach[A]]

    def productions_json(self):
        return [{"index": i, "head": h, "body": "".join(b) or EPS, "text": prod_str(h, b)}
                for i, (h, b) in enumerate(self.prods)]


def parse_grammar(text):
    """Reads a grammar in the format of Section 2.2 of the assignment:
    first line n, then n lines `A -> alt1 alt2 ...`."""
    if not isinstance(text, str):
        raise GrammarError("The grammar must be given as text.")
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise GrammarError("Empty grammar.")
    try:
        n = int(lines[0].strip())
    except ValueError:
        raise GrammarError(f"The first line must be the number of nonterminals, got {lines[0]!r}", 1)
    if n <= 0 or n > Grammar.MAX_NONTERMINALS:
        raise GrammarError(f"The number of nonterminals must be between 1 and {Grammar.MAX_NONTERMINALS}.", 1)
    body = [ln for ln in lines[1:] if ln.strip()]
    if len(body) != n:
        raise GrammarError(f"Expected {n} production lines but found {len(body)}.")
    return Grammar(body)


def fmt_set(s):
    """Assignment format: terminals in ASCII order, then e, then $."""
    out = sorted(x for x in s if x not in (EPS, END))
    if EPS in s:
        out.append(EPS)
    if END in s:
        out.append(END)
    return "{" + ", ".join(out) + "}"


def sets_lines(g):
    """The lines printed by --sets (alphabetical order of nonterminals)."""
    return ([f"First({A}) = {fmt_set(g.first[A])}" for A in g.nonterminals]
            + [f"Follow({A}) = {fmt_set(g.follow[A])}" for A in g.nonterminals])


def sets_json(g):
    ordered = lambda s: sorted(x for x in s if x not in (EPS, END)) + ([EPS] if EPS in s else []) + ([END] if END in s else [])
    return {
        "first": {A: ordered(g.first[A]) for A in g.nonterminals},
        "follow": {A: ordered(g.follow[A]) for A in g.nonterminals},
        "lines": sets_lines(g),
        "steps": {"first": g.first_events, "follow": g.follow_events},
    }
