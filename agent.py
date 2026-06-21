import json
import os
import re
from groq import Groq, BadRequestError
from dotenv import load_dotenv
from tools import inspect_csv, run_python, finish_report, CHARTS_DIR
from prompts import SYSTEM_PROMPT

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_csv",
            "description": "Read a CSV file and return its schema, column info, sample rows, and basic statistics. Always call this first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the CSV file"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Execute Python code to analyze the data. "
                "The namespace includes: df (DataFrame), pd (pandas), plt (matplotlib.pyplot), charts_dir (path to save charts). "
                "Print results to stdout. Save charts with plt.savefig()."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "csv_path": {"type": "string", "description": "Path to the CSV file"},
                    "description": {"type": "string", "description": "Short label for this analysis, e.g. 'Revenue by country' or 'Top 10 products by sales'"},
                },
                "required": ["code", "csv_path", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_report",
            "description": "Call this when all analyses are complete to compile the final executive report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "2-3 sentence executive summary of the dataset and most important findings",
                    },
                    "findings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific, quantified findings from the analysis",
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of actionable recommendations based on the findings",
                    },
                },
                "required": ["summary", "findings", "recommendations"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "inspect_csv": inspect_csv,
    "run_python": run_python,
    "finish_report": finish_report,
}


def _parse_tool_call_from_text(text: str):
    """
    Extract a tool call embedded as plain text. Llama 3.3 70B occasionally emits
    function calls inline rather than through the proper tool_calls API field.
    Returns (fn_name, fn_args) or (None, None) if no recognizable pattern found.
    """
    patterns = [
        r"<function=(\w+)\((\{.+?\})\)>",              # <function=name({json})>
        r"<function=(\w+)\s+(\{.+?\})\s*></function>",  # <function=name {json}></function>
        r"<function=(\w+)\s+(\{.+?\})\s*</function>",   # <function=name {json}</function>
        r"<function[/.](\w+)>(\{.+?\})</function[^>]*>",   # <function/name> or <function.name>
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return m.group(1), json.loads(m.group(2))
            except json.JSONDecodeError:
                return m.group(1), {}
    m = re.search(r"<function[=./](\w+)", text)
    if m:
        return m.group(1), {}
    return None, None


def _parse_failed_generation(error: BadRequestError):
    """
    Groq sometimes raises BadRequestError instead of returning a proper tool call
    when the model generates a malformed function invocation. The error body still
    contains the raw text the model produced, so we can parse it and execute the
    intended tool manually. Returns (None, None) for non-tool_use_failed errors.
    """
    try:
        detail = error.response.json()
        err = detail.get("error", {})
        if err.get("code") != "tool_use_failed":
            return None, None
        failed = err.get("failed_generation", "")
        return _parse_tool_call_from_text(failed)
    except Exception:
        pass
    return None, None


def _truncate(result: dict, max_chars: int = 1500) -> str:
    """Cap tool output before adding it to message history to avoid hitting token limits."""
    text = json.dumps(result)
    if len(text) > max_chars:
        return text[:max_chars] + "... [truncated]"
    return text


def run_agent(csv_path: str, status_callback=None):
    """Run the tool-calling loop until finish_report is called. Returns (report, charts)."""
    for f in CHARTS_DIR.glob("*.png"):
        f.unlink(missing_ok=True)

    messages = [
        {
            "role": "user",
            "content": (
                f"Analyze the business data in this CSV and generate an executive report "
                f"with key findings and recommendations. File: {csv_path}"
            ),
        }
    ]

    charts = []
    report = None
    python_calls = 0

    while True:
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=4096,
            )
        except BadRequestError as e:
            fn_name, fn_args = _parse_failed_generation(e)
            if fn_name is None:
                raise
            if fn_name not in TOOL_FUNCTIONS:
                break
            if fn_name == "inspect_csv":
                fn_args["path"] = csv_path
            elif fn_name == "run_python":
                fn_args["csv_path"] = csv_path
                if not fn_args.get("code"):
                    continue
            result = TOOL_FUNCTIONS[fn_name](**fn_args)
            if fn_name == "run_python" and result.get("charts"):
                charts.extend(result["charts"])
            if fn_name == "finish_report":
                report = result
                break
            # Non-terminal tool: inject result and keep looping
            fake_id = f"recovered_{fn_name}"
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": fake_id, "type": "function",
                                "function": {"name": fn_name, "arguments": json.dumps(fn_args)}}],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": fake_id,
                "content": _truncate(result),
            })
            continue

        message = response.choices[0].message
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (message.tool_calls or [])
            ] or None,
        })

        if not message.tool_calls:
            break

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            # Always inject the real path — LLM double-escapes Windows backslashes in JSON
            if fn_name == "inspect_csv":
                fn_args["path"] = csv_path
            elif fn_name == "run_python":
                fn_args["csv_path"] = csv_path

            if status_callback:
                status_callback(fn_name, fn_args)

            if fn_name == "finish_report" and python_calls < 3:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "error": f"Only {python_calls} analyses run so far. You must run at least 3 distinct run_python analyses before calling finish_report. Keep analyzing."
                    }),
                })
                continue

            result = TOOL_FUNCTIONS[fn_name](**fn_args)

            if fn_name == "run_python":
                python_calls += 1
                if result.get("charts"):
                    charts.extend(result["charts"])

            if fn_name == "finish_report":
                report = result

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": _truncate(result),
            })

        if report is not None:
            break

    return report, charts
