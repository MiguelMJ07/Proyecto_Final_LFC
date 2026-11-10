"""The size limits of the web server (2000 symbols per string, 400 LR(0) states, 400 productions) do not apply to
cli/main.py: the program of Section 2.2 must work for any grammar and any string. The server keeps its limits."""
import os
import subprocess
import sys

import pytest

from functions.cfg_grammar import GrammarError, parse_grammar
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1

CLI = os.path.join(os.path.dirname(__file__), "..", "cli", "main.py")

HUGE = "1\nS -> " + "a" * 450                      # LL(1) and SLR(1), with 452 LR(0) states
FIRST = "abcdfghijklmnopqrstuvwxyz"                  # 25 terminals (no 'e')
SECOND = "0123456789!#%&*+-"                         # 17 terminals
MANY = "1\nS -> " + " ".join(a + b for a in FIRST for b in SECOND)   # 425 productions


def run(stdin):
    out = subprocess.run([sys.executable, CLI], input=stdin, capture_output=True, text=True, timeout=120)
    return out.stdout.splitlines()


def test_cli_accepts_strings_longer_than_the_web_limit():
    w = "b" + "a" * 2500
    assert run("1\nS -> Sa b\n" + w + "\n" + w + "c\n\n") == ["Grammar is SLR(1).", "yes", "no"]
    w = "a" * 2500
    assert run("1\nS -> aS e\nT\n" + w + "\n\nB\n" + w + "\n\nQ\n") == [
        "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):", "yes",
        "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):", "yes",
        "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):"]


def test_cli_builds_lr0_collections_with_more_than_400_states():
    out = run(HUGE + "\nB\n" + "a" * 450 + "\n" + "a" * 449 + "\n\nQ\n")
    assert out == ["Select a parser (T: for LL(1), B: for SLR(1), Q: quit):", "yes", "no",
                   "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):"]


def test_cli_reads_grammars_with_more_than_400_productions():
    assert run(MANY + "\na0\n&&\nz-\n\n") == ["Grammar is SLR(1).", "yes", "no", "yes"]


def test_the_web_defaults_are_unchanged():
    g = parse_grammar("1\nS -> aS e")
    assert LL1(g).max_input == 2000 and SLR1(g).max_input == 2000 and SLR1(g).max_states == 400
    assert LL1(g).parse("a" * 2001)["error"] and not SLR1(g).parse("a" * 2001)["accepted"]
    assert SLR1(parse_grammar(HUGE)).too_big
    with pytest.raises(GrammarError):
        parse_grammar(MANY)
