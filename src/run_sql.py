"""
run_sql.py
----------
Runs every query in sql/business_questions.sql against data/warehouse.db,
prints the results, and saves them to reports/sql_results.md.

Run (after the pipeline):  python src/run_sql.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "warehouse.db"
QUERIES_PATH = PROJECT_ROOT / "sql" / "business_questions.sql"
RESULTS_PATH = PROJECT_ROOT / "reports" / "sql_results.md"


def load_queries(path=QUERIES_PATH):
    """Split the .sql file into a list of (name, description, sql_text).

    A new query starts at every line beginning with '-- name:'.
    The first comment line after the name (starting with '-- Q') is used
    as a human-readable description.
    """
    text = Path(path).read_text(encoding="utf-8")
    queries = []
    current_name = None
    current_lines = []

    for line in text.splitlines():
        if line.startswith("-- name:"):
            if current_name is not None:
                queries.append((current_name, current_lines))
            current_name = line.replace("-- name:", "").strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        queries.append((current_name, current_lines))

    result = []
    for name, lines in queries:
        description = ""
        for line in lines:
            if line.startswith("-- Q"):
                description = line.replace("--", "", 1).strip()
            elif description and line.startswith("--    "):
                # an indented comment line continues the question text
                description = description + " " + line.replace("--", "", 1).strip()
            elif description:
                break
        sql_text = "\n".join(lines).strip()
        result.append((name, description, sql_text))
    return result


def run_all(db_path=DB_PATH, queries_path=QUERIES_PATH):
    """Run each query and return a list of (name, description, DataFrame)."""
    connection = sqlite3.connect(db_path)
    results = []
    try:
        for name, description, sql_text in load_queries(queries_path):
            table = pd.read_sql_query(sql_text, connection)
            results.append((name, description, table))
    finally:
        connection.close()
    return results


def to_markdown_table(df):
    """Tiny Markdown table writer (avoids needing the 'tabulate' package)."""
    if df.empty:
        return "_(no rows returned)_"
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    divider = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = []
    for _, row in df.iterrows():
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:,.2f}")
            else:
                cells.append(str(value))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, divider] + rows)


def main():
    results = run_all()
    lines = ["# SQL Results", "",
             "> Output of `python src/run_sql.py` on the **synthetic** warehouse. "
             "Not real business data.", ""]
    for name, description, table in results:
        print("=" * 80)
        print(f"{name}: {description}")
        print("-" * 80)
        if table.empty:
            print("(no rows returned)")
        else:
            print(table.to_string(index=False))
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"**{description}**")
        lines.append("")
        lines.append(to_markdown_table(table))
        lines.append("")
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved {len(results)} query results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
