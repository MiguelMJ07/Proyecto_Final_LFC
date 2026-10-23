"""Tiny, safe expression language for semantic rules (no eval/exec, no attribute access).
Supported: numbers, strings, True/False, + - * // % /, comparisons, and/or/not, `a if c else b`,
and the functions max, min, abs, int, str, len. This is what lets an SDD be *data*."""
import ast
import operator

MAX_LEN = 400
MAX_NODES = 250
MAX_STR = 10000

FUNCS = {"max": max, "min": min, "abs": abs, "int": int, "str": str, "len": len}
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Div: operator.truediv}
CMPOPS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
          ast.Gt: operator.gt, ast.GtE: operator.ge}


class ExprError(ValueError):
    pass


def compile_expr(text, allowed_names):
    """Parses `text` and returns fn(env) -> value, where env maps each allowed name to a value."""
    if len(text) > MAX_LEN:
        raise ExprError(f"Expression longer than {MAX_LEN} characters.")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as e:
        raise ExprError(f"Syntax error in expression {text!r}: {e.msg}")
    count = sum(1 for _ in ast.walk(tree))
    if count > MAX_NODES:
        raise ExprError("Expression too complex.")
    node = tree.body
    _check(node, allowed_names)
    return lambda env: _ev(node, env)


def _check(n, names):
    if isinstance(n, ast.Constant):
        if not isinstance(n.value, (int, float, str, bool)) and n.value is not None:
            raise ExprError(f"Unsupported constant {n.value!r}")
    elif isinstance(n, ast.Name):
        if n.id not in names and n.id not in ("True", "False", "None"):
            raise ExprError(f"Unknown name {n.id!r}")
    elif isinstance(n, ast.BinOp):
        if type(n.op) not in BINOPS:
            raise ExprError(f"Operator {type(n.op).__name__} is not allowed")
        _check(n.left, names); _check(n.right, names)
    elif isinstance(n, ast.UnaryOp):
        if not isinstance(n.op, (ast.USub, ast.UAdd, ast.Not)):
            raise ExprError("Unsupported unary operator")
        _check(n.operand, names)
    elif isinstance(n, ast.BoolOp):
        for v in n.values:
            _check(v, names)
    elif isinstance(n, ast.Compare):
        if any(type(o) not in CMPOPS for o in n.ops):
            raise ExprError("Unsupported comparison")
        _check(n.left, names)
        for c in n.comparators:
            _check(c, names)
    elif isinstance(n, ast.IfExp):
        _check(n.test, names); _check(n.body, names); _check(n.orelse, names)
    elif isinstance(n, ast.Call):
        if not isinstance(n.func, ast.Name) or n.func.id not in FUNCS or n.keywords:
            raise ExprError(f"Only these functions are allowed: {', '.join(sorted(FUNCS))}")
        for a in n.args:
            _check(a, names)
    else:
        raise ExprError(f"Unsupported syntax: {type(n).__name__}")


def _ev(n, env):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.Name):
        if n.id in env:
            return env[n.id]
        return {"True": True, "False": False, "None": None}[n.id]
    if isinstance(n, ast.BinOp):
        a, b = _ev(n.left, env), _ev(n.right, env)
        if isinstance(n.op, ast.Mult) and (isinstance(a, str) or isinstance(b, str)):
            k = b if isinstance(a, str) else a
            s = a if isinstance(a, str) else b
            if not isinstance(k, int) or len(s) * max(k, 0) > MAX_STR:
                raise ExprError("String repetition too large")
        if isinstance(n.op, ast.Mult) and isinstance(a, int) and isinstance(b, int) and abs(a) * abs(b) > 10 ** 30:
            raise ExprError("Integer overflow guard")
        try:
            return BINOPS[type(n.op)](a, b)
        except ZeroDivisionError:
            raise ExprError("Division by zero")
        except TypeError as e:
            raise ExprError(str(e))
    if isinstance(n, ast.UnaryOp):
        v = _ev(n.operand, env)
        return -v if isinstance(n.op, ast.USub) else (+v if isinstance(n.op, ast.UAdd) else (not v))
    if isinstance(n, ast.BoolOp):
        vals = [_ev(v, env) for v in n.values]
        return all(vals) if isinstance(n.op, ast.And) else any(vals)
    if isinstance(n, ast.Compare):
        left = _ev(n.left, env)
        for op, c in zip(n.ops, n.comparators):
            right = _ev(c, env)
            try:
                if not CMPOPS[type(op)](left, right):
                    return False
            except TypeError as e:
                raise ExprError(str(e))
            left = right
        return True
    if isinstance(n, ast.IfExp):
        return _ev(n.body, env) if _ev(n.test, env) else _ev(n.orelse, env)
    if isinstance(n, ast.Call):
        try:
            return FUNCS[n.func.id](*[_ev(a, env) for a in n.args])
        except (TypeError, ValueError) as e:
            raise ExprError(f"{n.func.id}(): {e}")
    raise ExprError("Unsupported syntax")
