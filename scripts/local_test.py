"""Run Phase 1 parsing + keyword matching against a local file, no GCP needed.

Usage: python scripts/local_test.py /path/to/file.pdf [more files...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline" / "phase1_filter"))

from matcher import is_match  # noqa: E402
from parsers import extract_text  # noqa: E402


def main(paths: list[str]):
    for path in paths:
        text = extract_text(path)
        match = is_match(text)
        print(f"{path}: {'MATCH' if match else 'no match'} ({len(text)} chars extracted)")
        if match:
            print(text[:500])
            print("...\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
