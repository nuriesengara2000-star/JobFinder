from __future__ import annotations

import re
from typing import Any

TECH_KEYWORDS = {
    "python", "fastapi", "django", "flask", "sql", "postgres", "postgresql", "supabase",
    "react", "next", "next.js", "javascript", "typescript", "docker", "git", "ci/cd",
    "openai", "anthropic", "ollama", "llm", "rag", "langchain", "crewai", "langgraph",
    "agent", "agents", "multi-agent", "genai", "ai", "ml", "machine learning", "nlp",
    "pgvector", "vector", "hybrid search", "rrf", "lora", "qlora", "mcp", "n8n",
    "api", "rest", "backend", "automation", "devops",
}

AI_TERMS = {
    "ai", "genai", "llm", "rag", "langchain", "crewai", "openai", "anthropic",
    "ollama", "machine learning", "ml", "nlp", "agent", "agents", "multi-agent",
    "prompt", "prompt engineering", "fine-tuning", "lora", "qlora", "vector", "pgvector",
}

JUNIOR_TERMS = {"junior", "intern", "internship", "trainee", "стажер", "стажёр", "младший", "джуниор"}
SENIOR_TERMS = {"senior", "lead", "principal", "head", "director", "chief", "cto", "cdo", "architect", "руководитель", "директор", "главный", "ведущий"}

# Domains that are usually irrelevant for a GenAI / backend / frontend technical resume.
IRRELEVANT_DOMAIN_TERMS = {
    "юрист", "lawyer", "legal", "sales", "продаж", "менеджер по продаж", "маркетолог",
    "бухгалтер", "accountant", "hr", "recruiter", "директор по", "chief data officer",
}

WORD_RE = re.compile(r"[a-zа-яё0-9+#.\-/]+", re.IGNORECASE)


def _text(value: Any) -> str:
    return str(value or "").lower()


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in WORD_RE.finditer(text)}


def build_search_queries(parsed_resume: dict[str, Any]) -> list[str]:
    """Create focused search queries from the parsed resume.

    The ReAct agent can sometimes ask HH for too broad terms like "AI". These
    deterministic queries make the fallback search more aligned with the user's
    actual profile and seniority.
    """
    desired_role = _text(parsed_resume.get("desired_role")).strip()
    skills = [str(s).strip() for s in parsed_resume.get("skills", []) if str(s).strip()]
    skills_l = {s.lower() for s in skills}
    level = _text(parsed_resume.get("experience_level") or "junior")

    queries: list[str] = []

    if desired_role:
        queries.append(f"{level} {desired_role}".strip())
        queries.append(desired_role)

    if skills_l & AI_TERMS or "genai" in desired_role or "ai" in desired_role:
        queries.extend([
            "Junior GenAI Engineer Python LangChain",
            "Junior AI Engineer Python",
            "AI Engineer LangChain RAG",
            "LLM Engineer Python",
            "Machine Learning Engineer Junior Python",
            "Python Developer AI FastAPI",
        ])

    if {"fastapi", "python", "backend"} & skills_l:
        queries.extend(["Junior Python Developer FastAPI", "Python Backend Developer Junior"])

    if {"react", "next", "next.js", "javascript", "typescript"} & skills_l:
        queries.extend(["Junior React Developer", "Frontend Developer React Junior"])

    # Deduplicate while preserving order and keep queries short enough for job boards.
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        q = " ".join(query.split())
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            result.append(q[:120])
    return result[:8]


def rank_jobs(jobs: list[dict[str, Any]], parsed_resume: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    """Filter and rank job cards by resume relevance.

    Returns the same job dicts enriched with match_score, match_reason and
    level_warning fields for the frontend.
    """
    if not jobs:
        return []

    desired_role = _text(parsed_resume.get("desired_role"))
    level = _text(parsed_resume.get("experience_level") or "junior")
    resume_skills = [str(s).lower().strip() for s in parsed_resume.get("skills", []) if str(s).strip()]
    skill_terms = set(resume_skills) | {term for term in TECH_KEYWORDS if term in " ".join(resume_skills)}

    # Add useful terms from the desired role.
    role_tokens = _tokens(desired_role)
    skill_terms |= {t for t in role_tokens if len(t) > 1}

    ranked: list[tuple[int, dict[str, Any]]] = []
    seen_urls: set[str] = set()

    for raw_job in jobs:
        job = dict(raw_job)
        url = str(job.get("url") or "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        title = _text(job.get("title"))
        company = _text(job.get("company"))
        requirements = _text(job.get("requirements"))
        haystack = f"{title} {company} {requirements}"

        if any(term in haystack for term in IRRELEVANT_DOMAIN_TERMS):
            # Keep only if it has very strong technical overlap; otherwise remove.
            tech_overlap = sum(1 for term in skill_terms if term and term in haystack)
            if tech_overlap < 3:
                continue

        score = 0
        reasons: list[str] = []

        # Role/title relevance is the strongest signal.
        if "genai" in title or "ai" in title or "llm" in title or "machine learning" in title or "ml" in title:
            score += 30
            reasons.append("AI/GenAI бағытындағы вакансия")
        if "python" in title or "backend" in title or "developer" in title or "engineer" in title:
            score += 18
            reasons.append("техникалық engineering role")
        if desired_role and any(tok in title for tok in role_tokens if len(tok) > 2):
            score += 18

        matched_skills = [term for term in skill_terms if len(term) > 1 and term in haystack]
        score += min(len(matched_skills) * 6, 36)
        if matched_skills:
            reasons.append("skills match: " + ", ".join(matched_skills[:5]))

        # Seniority handling: junior candidate should not receive director/senior roles on top.
        has_junior = any(term in haystack for term in JUNIOR_TERMS)
        has_senior = any(term in haystack for term in SENIOR_TERMS)
        level_warning = ""
        if level == "junior":
            if has_junior:
                score += 20
                reasons.append("junior/trainee деңгейіне жақын")
            if has_senior:
                score -= 45
                level_warning = "Бұл вакансия senior/lead деңгейінде болуы мүмкін."
        elif level == "middle" and has_senior:
            score -= 18
            level_warning = "Бұл вакансия жоғары деңгей болуы мүмкін."

        # Remote tech boards are relevant for AI/backend roles, but still need skill overlap.
        source = _text(job.get("source"))
        if source in {"remoteok", "wwr", "linkedin"} and matched_skills:
            score += 8

        # Strongly push down non-technical generic management roles.
        if any(term in title for term in ["director", "chief", "cdo", "директор", "менеджер по продаж"]):
            score -= 35

        if score < 18:
            continue

        job["match_score"] = max(0, min(100, score))
        job["match_reason"] = "; ".join(reasons[:3]) or "релевантность определена по названию и описанию вакансии"
        if level_warning:
            job["level_warning"] = level_warning
        ranked.append((score, job))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [job for _, job in ranked[:limit]]


def format_ranked_answer(jobs: list[dict[str, Any]], parsed_resume: dict[str, Any]) -> str:
    role = parsed_resume.get("desired_role") or "target role"
    level = parsed_resume.get("experience_level") or "junior"
    if not jobs:
        return (
            f"Я не нашёл достаточно релевантных вакансий под профиль {level} {role}. "
            "Попробуй расширить локацию до Remote/Europe или убрать слишком узкие фильтры."
        )

    lines = [
        f"Ниже вакансии, отфильтрованные под профиль: {level} {role}.",
        "Я убрал явно нерелевантные позиции вроде sales/legal/director, если они не совпадали с technical skills.\n",
    ]
    for idx, job in enumerate(jobs, start=1):
        lines.append(f"{idx}. **{job.get('title') or 'Untitled role'}** — {job.get('company') or 'Company not specified'} [{job.get('source') or 'source'}]")
        if job.get("salary"):
            lines.append(f"   💰 {job['salary']}")
        if job.get("match_score") is not None:
            lines.append(f"   ⭐ Match score: {job['match_score']}/100")
        if job.get("match_reason"):
            lines.append(f"   ✅ {job['match_reason']}")
        if job.get("level_warning"):
            lines.append(f"   ⚠️ {job['level_warning']}")
        if job.get("requirements"):
            lines.append(f"   📝 {str(job['requirements'])[:240]}")
        if job.get("url"):
            lines.append(f"   🔗 {job['url']}")
        lines.append("")
    return "\n".join(lines).strip()
