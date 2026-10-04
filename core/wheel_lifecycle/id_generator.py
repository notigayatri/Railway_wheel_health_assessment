import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "railway.db"


def generate_asset_id():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT asset_id FROM wheels ORDER BY asset_id DESC")
    rows = cursor.fetchall()
    conn.close()

    # Find the highest valid WH###### ID, skipping any malformed entries
    max_num = 0
    for (aid,) in rows:
        if isinstance(aid, str) and aid.startswith("WH") and aid[2:].isdigit():
            max_num = max(max_num, int(aid[2:]))

    return f"WH{max_num + 1:06d}"


def generate_inspection_id():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT inspection_id FROM inspections ORDER BY inspection_id DESC LIMIT 1"
    )

    row = cursor.fetchone()

    if row is None:
        next_id = 1
    else:
        next_id = int(row[0][3:]) + 1

    conn.close()

    return f"INS{next_id:06d}"