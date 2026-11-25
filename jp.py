"""Add a hand-written batch to the study data.

Usage:
  .venv/bin/python jp.py add batch.json

The batch format is documented in brain/store.py.
"""
import json
import sys
from pathlib import Path

from brain.store import Store

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "add":
        sys.exit(__doc__)
    Store(Path(__file__).parent).add(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    print("Saved japanese.xlsx and grammar.md")
