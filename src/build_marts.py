"""Run the SQL models (01-05) in order and persist them to a DuckDB file."""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "sona.duckdb"
MODELS = ["01_staging.sql", "02_int_user_funnel.sql", "03_int_week1_behaviour.sql",
          "04_int_retention.sql", "05_mart_user_activation.sql"]


def connect(read_only=False):
    import os
    os.chdir(ROOT)                      # SQL uses paths relative to the project root
    return duckdb.connect(str(DB), read_only=read_only)


def load_named_queries(path=ROOT / "sql" / "06_analysis_queries.sql"):
    """Parse '-- name: x' blocks into {name: sql}."""
    text = Path(path).read_text()
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    return {blocks[i]: blocks[i + 1].strip().rstrip(";") for i in range(1, len(blocks), 2)}


def build():
    con = connect()
    for m in MODELS:
        con.execute((ROOT / "sql" / m).read_text())
        print("built", m)
    n = con.execute("SELECT count(*) FROM mart_user_activation").fetchone()[0]
    print(f"mart_user_activation rows: {n:,}")
    con.close()


if __name__ == "__main__":
    build()
