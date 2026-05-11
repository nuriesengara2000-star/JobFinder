"""Entry point for the AI job-search agent.

Usage::

    python main.py

You will be prompted to paste a resume. Finish the input with:

* Windows:  blank line, then Ctrl+Z, then Enter
* Unix:     Ctrl+D

The agent then runs the ReAct loop and prints a list of REAL jobs from hh.kz.

Alternatively pipe a file in:

    python main.py < my_resume.txt
"""

from __future__ import annotations

import logging
import os
import sys

# Force UTF-8 on Windows consoles so Cyrillic job titles render correctly.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# Load .env from the script's own folder first, then walk upward (this catches
# the parent project's .env that already holds OPENAI_API_KEY).
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

try:  # works for `python -m react_agent.main` from project root
    from .agent import JobSearchAgent  # noqa: E402
except ImportError:  # works for `python main.py` from inside react_agent/
    from agent import JobSearchAgent  # noqa: E402


def _read_resume() -> str:
    """Read the full resume text from stdin (multi-line)."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("Paste your resume below.")
    print("When done: blank line, then Ctrl+Z + Enter (Windows) or Ctrl+D (Unix).\n")
    try:
        data = sys.stdin.read()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    return data.strip()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    resume = _read_resume()
    if not resume:
        print("ERROR: empty resume.")
        sys.exit(1)

    agent = JobSearchAgent()

    print("\n=== Running ReAct agent ===\n")
    final_answer = agent.run(resume)

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(final_answer)


if __name__ == "__main__":
    main()
