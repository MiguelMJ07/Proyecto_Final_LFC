# GATEWAY layer for the LaTeX export (report tables). Any failure becomes a ValueError (HTTP 400).
from functions.cfg_sdd import evaluate
from functions.latex_export import grammar_report, sdd_report
from gateways.grammar_gateway import GrammarGateway
from gateways.sdd_gateway import SDDGateway

MAX_STRINGS = 10


class ExportGateway:

    def grammar(self, data):
        g = GrammarGateway().load(data["grammar"])
        strings = data.get("inputs", [])
        if (not isinstance(strings, list) or len(strings) > MAX_STRINGS or not all(isinstance(x, str) and len(x) <= 60 for x in strings)):
            raise ValueError(f"'inputs' must be a list of at most {MAX_STRINGS} short strings.")
        parser = data.get("parser", "auto")
        if parser not in ("auto", "ll1", "slr1"):
            raise ValueError("'parser' must be 'auto', 'll1' or 'slr1'.")
        title = str(data.get("title", "Grammar analysis"))[:80]
        return {"filename": "grammar_report.tex", "tex": grammar_report(g, strings, parser, title)}

    def sdd(self, data):
        sdd = SDDGateway()._load(data)
        inp = data.get("input")
        result = None
        if inp is not None:
            if not isinstance(inp, str) or len(inp) > 80:
                raise ValueError("'input' must be a string of at most 80 symbols.")
            result = evaluate(sdd, "" if inp.strip() == "e" else inp.strip())
        return {"filename": "sdd_report.tex", "tex": sdd_report(sdd, result)}
