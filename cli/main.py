"""Items 1 and 2 from the command line, with the input/output protocol of Section 2.2 of the assignment.

    python cli/main.py [--sets] [--tables] [--trace] < input

--sets    print FIRST and FOLLOW after reading the grammar (required by the assignment)
--tables  also print the LL(1) table and the LR(0) automaton with the SLR(1) tables (extra)
--trace   print every parsing step (extra, handy for the report)
The protocol itself lives in src/functions/cfg_protocol.py; POST /grammar/report runs the same code, so the
web server answers exactly what this program prints."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from functions.cfg_ll1 import LL1                                                      # noqa: E402
from functions.cfg_protocol import line_reader, read_grammar, run_session              # noqa: E402
from functions.cfg_slr1 import SLR1                                                    # noqa: E402


def write(line):
    print(line)
    sys.stdout.flush()           # the prompt must be visible before the program waits for the answer


def main():
    args = sys.argv[1:]
    read_line = line_reader(sys.stdin.readline)
    try:
        g = read_grammar(read_line)
    except ValueError as e:      # GrammarError is a ValueError
        print(f"Invalid grammar: {e}")
        return 1
    run_session(g, LL1(g), SLR1(g), read_line, write,
                sets="--sets" in args, tables="--tables" in args, trace="--trace" in args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
