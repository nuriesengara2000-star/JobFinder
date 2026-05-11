from backend.app.services.job_matching import rank_jobs


def test_rank_jobs_filters_non_technical_roles_for_ai_candidate():
    parsed_resume = {
        "level": "junior",
        "target_role": "Junior GenAI Engineer",
        "skills": ["Python", "FastAPI", "LangChain", "RAG", "OpenAI"],
    }
    jobs = [
        {
            "title": "Junior AI Engineer",
            "company": "AI Startup",
            "description": "Python, FastAPI, LangChain, RAG, OpenAI APIs",
            "source": "test",
            "url": "https://example.com/ai",
        },
        {
            "title": "Юрист",
            "company": "Legal Company",
            "description": "Legal documents and Kazakhstan law",
            "source": "test",
            "url": "https://example.com/legal",
        },
    ]

    ranked = rank_jobs(jobs, parsed_resume, limit=5)

    assert ranked
    assert ranked[0]["title"] == "Junior AI Engineer"
    assert all(job["title"] != "Юрист" for job in ranked)
