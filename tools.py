import time
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend, required for server environments
import matplotlib.pyplot as plt
import io
import sys
import traceback
from pathlib import Path

CHARTS_DIR = Path(__file__).parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)


def inspect_csv(path: str) -> dict:
    df = pd.read_csv(path, encoding='latin-1')

    columns = []
    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_pct": round(df[col].isnull().mean() * 100, 2),
            "unique_count": int(df[col].nunique()),
        }
        if df[col].dtype == object:
            col_info["sample_values"] = df[col].dropna().unique()[:5].tolist()
        columns.append(col_info)

    numeric_cols = df.select_dtypes(include="number")
    return {
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "columns": columns,
        "sample": df.head(5).to_string(),
        "numeric_summary": numeric_cols.describe().to_string() if not numeric_cols.empty else "No numeric columns",
    }


def run_python(code: str, csv_path: str, description: str = None) -> dict:
    """
    Execute LLM-generated code in an isolated namespace and return stdout + any new charts.

    Charts are detected by mtime: only files modified after execution started are reported,
    so re-runs don't pick up charts from a previous analysis session.
    """
    df = pd.read_csv(csv_path, encoding='latin-1')
    plt.close("all")

    namespace = {
        "pd": pd,
        "plt": plt,
        "df": df,
        "charts_dir": str(CHARTS_DIR),
        "__builtins__": __builtins__,
    }

    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    t0 = time.time()

    try:
        exec(code, namespace)
        output = buffer.getvalue()
    except Exception:
        output = f"ERROR:\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout
        plt.close("all")

    new_charts = [
        str(p) for p in CHARTS_DIR.glob("*.png")
        if p.stat().st_mtime >= t0 - 0.5
    ]
    return {"output": output, "charts": new_charts}


def finish_report(summary: str, findings: list, recommendations: list) -> dict:
    # Strip findings that describe code steps rather than business insights
    clean_findings = [
        f for f in findings
        if not any(kw in f.lower() for kw in ["chart_", "saved to", "plotted and saved", ".png"])
    ]
    return {"summary": summary, "findings": clean_findings, "recommendations": recommendations}
