"""
General-purpose utility tools: calculator, date/time, timezone converter.
"""
import ast
import math
import operator
import re
import zoneinfo
from datetime import datetime, timezone

from backend.tools.base import Tool, ToolResult


# ── Safe calculator ───────────────────────────────────────────────────────────

_SAFE_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "abs": abs, "round": round, "sqrt": math.sqrt,
    "log": math.log, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "ceil": math.ceil, "floor": math.floor,
    "pi": math.pi, "e": math.e,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {node.op}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary op: {node.op}")
        return op(_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named functions allowed")
        fn = _SAFE_FUNCS.get(node.func.id)
        if not fn:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)
    if isinstance(node, ast.Name):
        val = _SAFE_FUNCS.get(node.id)
        if val is None:
            raise ValueError(f"Unknown name: {node.id}")
        return val
    raise ValueError(f"Unsupported expression: {type(node)}")


class CalculatorTool(Tool):
    name = "calculator"
    description = (
        "Evaluate a mathematical expression and return the result. "
        "Supports: +, -, *, /, **, %, sqrt(), sin(), cos(), tan(), log(), "
        "log10(), abs(), round(), ceil(), floor(), pi, e. "
        "Use this for any arithmetic or math calculation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression to evaluate, e.g. '2 ** 10', 'sqrt(144)', '(12 * 3.5) / 2'",
            }
        },
        "required": ["expression"],
    }

    async def run(self, expression: str, **_) -> ToolResult:
        try:
            cleaned = expression.strip()
            # Replace ^ with ** for user convenience
            cleaned = cleaned.replace("^", "**")
            tree = ast.parse(cleaned, mode="eval")
            result = _safe_eval(tree)
            # Clean up float display
            if isinstance(result, float) and result == int(result):
                display = str(int(result))
            else:
                display = f"{result:.10g}"
            return ToolResult(ok=True, data={"expression": expression, "result": display})
        except ZeroDivisionError:
            return ToolResult(ok=False, error="Division by zero")
        except Exception as exc:
            return ToolResult(ok=False, error=f"Cannot evaluate '{expression}': {exc}")


# ── Date / Time ───────────────────────────────────────────────────────────────

class DateTimeTool(Tool):
    name = "get_datetime"
    description = (
        "Get the current date and time. Optionally specify a timezone. "
        "Use this whenever the user asks about the current date, time, day, or year."
    )
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": (
                    "IANA timezone name, e.g. 'Asia/Kolkata', 'America/New_York', 'UTC'. "
                    "Defaults to UTC if not specified."
                ),
            }
        },
        "required": [],
    }

    async def run(self, timezone: str = "UTC", **_) -> ToolResult:
        try:
            tz = zoneinfo.ZoneInfo(timezone)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError):
            return ToolResult(ok=False, error=f"Unknown timezone: '{timezone}'. Use IANA names like 'Asia/Kolkata'.")
        now = datetime.now(tz)
        return ToolResult(ok=True, data={
            "timezone":   timezone,
            "datetime":   now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "date":       now.strftime("%A, %d %B %Y"),
            "time":       now.strftime("%I:%M %p"),
            "iso":        now.isoformat(),
            "day_of_week": now.strftime("%A"),
            "unix_ts":    int(now.timestamp()),
        })


class TimezoneConverterTool(Tool):
    name = "convert_timezone"
    description = (
        "Convert a date/time from one timezone to another. "
        "Use when the user wants to know what time it is in a different city or country."
    )
    parameters = {
        "type": "object",
        "properties": {
            "datetime_str": {
                "type": "string",
                "description": "Date and time to convert, e.g. '2025-06-30 14:00'. Defaults to now.",
            },
            "from_timezone": {
                "type": "string",
                "description": "Source IANA timezone, e.g. 'America/New_York'.",
            },
            "to_timezone": {
                "type": "string",
                "description": "Target IANA timezone, e.g. 'Asia/Kolkata'.",
            },
        },
        "required": ["from_timezone", "to_timezone"],
    }

    async def run(self, from_timezone: str, to_timezone: str, datetime_str: str = "", **_) -> ToolResult:
        try:
            from_tz = zoneinfo.ZoneInfo(from_timezone)
            to_tz   = zoneinfo.ZoneInfo(to_timezone)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError) as exc:
            return ToolResult(ok=False, error=f"Unknown timezone: {exc}")

        try:
            if datetime_str:
                dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=from_tz)
            else:
                dt = datetime.now(from_tz)
        except ValueError:
            return ToolResult(ok=False, error="Invalid datetime format. Use 'YYYY-MM-DD HH:MM'.")

        converted = dt.astimezone(to_tz)
        return ToolResult(ok=True, data={
            "original":      dt.strftime("%Y-%m-%d %H:%M %Z"),
            "converted":     converted.strftime("%Y-%m-%d %H:%M %Z"),
            "from_timezone": from_timezone,
            "to_timezone":   to_timezone,
        })
