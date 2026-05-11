"""ReAct-style orchestration for the multi-source job-search agent.

The agent runs a strict Thought / Action / Observation loop. It MUST call
at least one search tool successfully before producing a Final Answer; the
Final Answer must contain only real jobs returned by the search tools.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable

from openai import OpenAI

try:  # package-style import (when run as `python -m react_agent.main`)
    from .tools import (
        hh_search_jobs,
        linkedin_search_jobs,
        parse_resume,
        remoteok_search_jobs,
        wwr_search_jobs,
    )
except ImportError:  # script-style import (when run as `python main.py`)
    from tools import (  # type: ignore
        hh_search_jobs,
        linkedin_search_jobs,
        parse_resume,
        remoteok_search_jobs,
        wwr_search_jobs,
    )

LOG = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a ReAct-style AI job-search agent. You help the user find REAL job
vacancies from multiple sources based on their resume.

You have access to FIVE tools:

1. parse_resume[resume]
   - Argument: literal token "resume" (system supplies the actual text).
   - Returns: JSON {skills, desired_role, experience_level}.

2. hh_search_jobs[<query> | area=40 | per_page=15]
   - HeadHunter (hh.kz default — area=40 = Kazakhstan, 113 = Russia, 1 = Moscow).
   - Russian/English queries both work.

3. linkedin_search_jobs[<query> | location=Kazakhstan | per_page=15]
   - LinkedIn public job search. `location` is free-text ("Kazakhstan",
     "Almaty", "Remote", "United States", "European Union" etc.).
   - English queries work best.

4. remoteok_search_jobs[<query> | per_page=15]
   - RemoteOK feed of REMOTE tech jobs worldwide. Use English keywords
     ("python backend", "react frontend", "devops").

5. wwr_search_jobs[<query> | per_page=15]
   - We Work Remotely RSS (programming categories). REMOTE only.

Each search tool returns a JSON list of jobs:
   {title, company, salary, requirements, url, source}

You MUST follow this exact format. Each step is one of:

Thought: <one or two sentences>
Action: <tool_name>[<arguments>]

After each Action the system appends:

Observation: <tool result as JSON>

When you have collected at least 10 real jobs across tools, output:

Thought: I have enough real jobs to answer.
Final Answer:
<formatted job list>

STRATEGY:
- FIRST action MUST be: Action: parse_resume[resume]
- Use the parsed desired_role, skills and experience_level to build specific queries.
- For junior candidates, prioritize queries with Junior / Intern / Trainee and avoid
  senior, lead, director, chief, CDO/CTO roles unless there are no alternatives.
- Then call hh_search_jobs (the user is in Kazakhstan — start local) with a focused
  query such as "Junior GenAI Engineer Python LangChain" or "Junior Python Developer AI",
  not a broad query like just "AI" or "data".
- If the resume mentions remote-friendly tech skills, ALSO call linkedin_search_jobs,
  remoteok_search_jobs and wwr_search_jobs for broader coverage.
- If a search returns 0/weak results, retry with a refined query
  (drop only overly narrow words, try Russian/English variants on HH, switch to broader
  English keywords on LinkedIn / RemoteOK / WWR).
- Do not include obviously irrelevant roles such as lawyer, sales manager, HR, accountant,
  data director/CDO, or non-technical management roles for a technical AI/software resume.

STRICT RULES:
- NEVER invent jobs. Every job in Final Answer must come from a successful
  search Observation in this conversation.
- Aim for at least 10 jobs in Final Answer (≥3 if some sources fail entirely).
- Maximum 10 tool calls total. After the 10th, you MUST output Final Answer.
- Final Answer format — one entry per job:
    N. **Title** — Company [source]
       💰 Salary (omit line if none)
       📝 Short description (one or two lines)
       🔗 Direct link
"""


_ACTION_RE = re.compile(r"Action:\s*([A-Za-z_]\w*)\s*\[(.*?)\]", re.DOTALL)


class JobSearchAgent:
    """Run the ReAct loop until the model produces a Final Answer."""

    def __init__(self, model: str | None = None, max_steps: int = 12) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in the environment")
        self.client = OpenAI(api_key=api_key)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.max_steps = max_steps
        self._resume_text = ""
        self._tool_calls = 0
        self._got_real_jobs = False

        # Public, populated as the loop runs — the bot reads these post-run
        # to render enriched cards via analyzer.analyze_jobs.
        self.parsed_resume: dict[str, Any] = {}
        self.collected_jobs: list[dict[str, Any]] = []
        self._seen_urls: set[str] = set()

        self.tools: dict[str, Callable[[str], Any]] = {
            "parse_resume": self._call_parse_resume,
            "hh_search_jobs": self._call_hh_search_jobs,
            "linkedin_search_jobs": self._call_linkedin_search_jobs,
            "remoteok_search_jobs": self._call_remoteok_search_jobs,
            "wwr_search_jobs": self._call_wwr_search_jobs,
        }

    # ------------------------------------------------------------------ run

    def run(self, resume_text: str) -> str:
        """Execute the ReAct loop and return the Final Answer string.

        After ``run`` returns, ``self.parsed_resume`` and ``self.collected_jobs``
        are populated with the structured artefacts the loop produced.
        """
        self._resume_text = resume_text
        self._tool_calls = 0
        self._got_real_jobs = False
        self.parsed_resume = {}
        self.collected_jobs = []
        self._seen_urls = set()

        user_prompt = (
            "Find at least 10 REAL job vacancies for the user, drawing from "
            "multiple sources where appropriate.\n"
            "The user's resume text is held by the system and will be passed to "
            "parse_resume automatically when you call parse_resume[resume].\n\n"
            "Begin."
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        for step in range(1, self.max_steps + 1):
            LOG.info("ReAct step %d/%d", step, self.max_steps)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                stop=["\nObservation:"],
            )
            chunk = (response.choices[0].message.content or "").strip()
            print(chunk)
            print()

            if "Final Answer:" in chunk:
                if not self._got_real_jobs:
                    LOG.warning("Model produced Final Answer without real jobs - rejecting")
                    messages.append({"role": "assistant", "content": chunk})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Observation: ERROR - you produced Final Answer before "
                            "any successful search call returned real jobs. Call "
                            "a search tool first. Continue in ReAct format."
                        ),
                    })
                    continue
                return self._extract_final_answer(chunk)

            match = _ACTION_RE.search(chunk)
            if match is None:
                LOG.warning("No Action found in step %d output", step)
                messages.append({"role": "assistant", "content": chunk})
                messages.append({
                    "role": "user",
                    "content": (
                        "Observation: ERROR - your previous reply did not contain a "
                        "valid `Action: <tool>[<args>]` line. Continue strictly in "
                        "ReAct format."
                    ),
                })
                continue

            tool_name = match.group(1).strip()
            tool_args = match.group(2).strip()

            observation = self._dispatch(tool_name, tool_args)

            messages.append({"role": "assistant", "content": chunk})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

            print(f"Observation: {observation}\n")

        # Out of steps — force the model to commit to a final answer.
        LOG.warning("Max steps reached - forcing Final Answer")
        messages.append({
            "role": "user",
            "content": (
                "You have reached the maximum number of steps. Output `Final Answer:` "
                "now using ONLY the real jobs you have already received from search "
                "tools in this conversation."
            ),
        })
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
        )
        chunk = (response.choices[0].message.content or "").strip()
        print(chunk)
        return self._extract_final_answer(chunk)

    # ---------------------------------------------------------------- dispatch

    def _dispatch(self, tool_name: str, tool_args: str) -> str:
        fn = self.tools.get(tool_name)
        if fn is None:
            return f"ERROR: unknown tool {tool_name!r}. Available tools: {list(self.tools)}"

        self._tool_calls += 1
        try:
            result = fn(tool_args)
        except Exception as exc:  # noqa: BLE001
            LOG.exception("Tool %s raised", tool_name)
            return f"ERROR: tool {tool_name} raised: {exc!r}"

        if tool_name in {
            "hh_search_jobs",
            "linkedin_search_jobs",
            "remoteok_search_jobs",
            "wwr_search_jobs",
        } and isinstance(result, list):
            real = [r for r in result if isinstance(r, dict) and r.get("url") and "error" not in r]
            if real:
                self._got_real_jobs = True
            # Accumulate (deduped by URL) for the post-run analyzer pass.
            for job in real:
                url = job.get("url")
                if url and url not in self._seen_urls:
                    self._seen_urls.add(url)
                    self.collected_jobs.append(job)

        try:
            return json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(result)

    # ---------------------------------------------------------------- tool callbacks

    def _call_parse_resume(self, args: str) -> dict[str, Any]:
        if args.strip().lower() in {"", "resume", '"resume"', "'resume'"}:
            text = self._resume_text
        else:
            text = args
        result = parse_resume(text)
        if isinstance(result, dict):
            self.parsed_resume = result
        return result

    def _call_hh_search_jobs(self, args: str) -> list[dict[str, Any]]:
        query, kwargs = _parse_args(args, allowed_int_keys={"area", "per_page"})
        return hh_search_jobs(
            query,
            area=int(kwargs.get("area", 40)),
            per_page=int(kwargs.get("per_page", 15)),
        )

    def _call_linkedin_search_jobs(self, args: str) -> list[dict[str, Any]]:
        query, kwargs = _parse_args(args, allowed_int_keys={"per_page"}, allowed_str_keys={"location"})
        return linkedin_search_jobs(
            query,
            location=str(kwargs.get("location", "Kazakhstan")),
            per_page=int(kwargs.get("per_page", 15)),
        )

    def _call_remoteok_search_jobs(self, args: str) -> list[dict[str, Any]]:
        query, kwargs = _parse_args(args, allowed_int_keys={"per_page"})
        return remoteok_search_jobs(query, per_page=int(kwargs.get("per_page", 15)))

    def _call_wwr_search_jobs(self, args: str) -> list[dict[str, Any]]:
        query, kwargs = _parse_args(args, allowed_int_keys={"per_page"})
        return wwr_search_jobs(query, per_page=int(kwargs.get("per_page", 15)))

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _extract_final_answer(chunk: str) -> str:
        if "Final Answer:" in chunk:
            return chunk.split("Final Answer:", 1)[1].strip()
        return chunk.strip()


def _parse_args(
    args: str,
    *,
    allowed_int_keys: set[str] | None = None,
    allowed_str_keys: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Parse ``"<query> | key=value | key=value"`` into (query, {key: value})."""
    allowed_int_keys = allowed_int_keys or set()
    allowed_str_keys = allowed_str_keys or set()
    text = args.strip().strip('"').strip("'")
    if "|" not in text:
        return text, {}
    parts = [p.strip() for p in text.split("|")]
    query = parts[0]
    kw: dict[str, Any] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip().lower(), v.strip()
        if k in allowed_int_keys and v.isdigit():
            kw[k] = int(v)
        elif k in allowed_str_keys:
            kw[k] = v
    return query, kw
