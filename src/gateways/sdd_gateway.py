# GATEWAY layer for Item 3 (SDD): loads a preset or a user-supplied definition (data) and runs the
# generic evaluator. Any internal error becomes a ValueError (-> HTTP 400).
from functions.cfg_sdd import SDD, SDDError, evaluate, with_circular_variant
from functions.cfg_sdd_presets import PRESETS

MAX_INPUTS = 50
MAX_INPUT_LEN = 400
MAX_DEFINITION_CHARS = 40000


class SDDGateway:

    def presets(self):
        out = []
        for p in PRESETS.values():
            d = SDD(p).describe()
            out.append({"id": p["id"], "name": p["name"], "description": p["description"],
                        "samples": p["samples"], "classification": d["classification"]["verdict"]})
        return out

    def preset(self, pid):
        if pid not in PRESETS:
            raise KeyError(pid)
        return {k: v for k, v in PRESETS[pid].items()}

    def _load(self, data):
        if "definition" in data:
            d = data["definition"]
            if not isinstance(d, dict):
                raise SDDError("Field 'definition' must be an SDD object.")
            if len(str(d)) > MAX_DEFINITION_CHARS:
                raise SDDError("SDD definition too large.")
        else:
            pid = data.get("preset", "luhn")
            if pid not in PRESETS:
                raise SDDError(f"Unknown preset {pid!r}. Available: {', '.join(PRESETS)}.")
            d = PRESETS[pid]
        if data.get("circular"):
            d = with_circular_variant(d)
        return SDD(d)

    def describe(self, data):
        return self._load(data).describe()

    def evaluate(self, data):
        sdd = self._load(data)
        inputs = data.get("inputs", data.get("input"))
        if isinstance(inputs, str):
            inputs = [inputs]
        if (not isinstance(inputs, list) or not inputs or len(inputs) > MAX_INPUTS
                or not all(isinstance(s, str) for s in inputs)):
            raise SDDError(f"Provide 'input' (string) or 'inputs' (1 to {MAX_INPUTS} strings).")
        results = []
        for s in inputs:
            w = "" if s.strip() == "e" else s.strip()
            if len(w) > MAX_INPUT_LEN:
                raise SDDError(f"Input longer than {MAX_INPUT_LEN} symbols.")
            r = evaluate(sdd, w)
            results.append(r)
        return {"sdd": sdd.name, "main": f"{sdd.main[0]}.{sdd.main[1]}", "results": results,
                "classification": sdd.classify()["verdict"]}
