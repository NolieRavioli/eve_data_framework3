"""tests/test_grab_structures.py
--------------------------------
Dumps the ``structures`` table from the public DuckDB warehouse to
``tests/structures.csv`` (i.e. ``./structures.csv`` relative to this file).
"""

import os
import sys

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.db.public import connect

OUTPUT = os.path.join(os.path.dirname(__file__), "structures.csv")

con = connect(read_only=True)
try:
    con.execute(f"COPY structures TO '{OUTPUT}' (HEADER, DELIMITER ',')")
    count = con.execute("SELECT COUNT(*) FROM structures").fetchone()[0]
    print(f"Exported {count} rows to {OUTPUT}")
finally:
    con.close()
