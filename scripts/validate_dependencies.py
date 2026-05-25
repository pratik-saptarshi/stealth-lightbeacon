#!/usr/bin/env python3
"""Validate pinned dependencies against live indices with pip-compile."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
EXTRA_INDEX_URL = "https://pypi.org/simple"


def main() -> int:
    try:
        import piptools  # noqa: F401
    except ImportError:
        print(
            "pip-tools is required for dependency validation. "
            "Install pre-commit or pip-tools and retry.",
            file=sys.stderr,
        )
        return 1

    with tempfile.NamedTemporaryFile(prefix="requirements-", suffix=".txt", delete=False) as handle:
        compiled = pathlib.Path(handle.name)

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piptools",
                "compile",
                "--resolver=backtracking",
                "--extra-index-url",
                EXTRA_INDEX_URL,
                "--quiet",
                "--output-file",
                str(compiled),
                str(REQUIREMENTS),
            ],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    finally:
        compiled.unlink(missing_ok=True)

    print("Dependency validation passed against live indices.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
