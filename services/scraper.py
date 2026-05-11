from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class JobListing:
    title: str
    company: str
    description: str
    link: str


# ---------------------------------------------------------------------------
# Mock data — replace MOCK_JOBS or swap get_jobs() body for real scraping.
# Interface contract: get_jobs() must always return list[JobListing], async.
# ---------------------------------------------------------------------------

MOCK_JOBS: list[JobListing] = [
    JobListing(
        title="Junior AI Engineer",
        company="NeuralPath",
        description=(
            "Build and fine-tune LLMs for enterprise clients. "
            "Stack: Python, PyTorch, Hugging Face Transformers, FastAPI. "
            "Nice to have: Docker, Kubernetes, AWS SageMaker."
        ),
        link="https://jobs.example.com/neuralpath-junior-ai",
    ),
    JobListing(
        title="LLM Integration Engineer",
        company="AutomatAI",
        description=(
            "Integrate large language models into enterprise workflows using LangChain and custom agents. "
            "Requirements: Python, LangChain, OpenAI API, vector databases (Pinecone or Weaviate). "
            "Knowledge of RAG architectures and prompt engineering preferred."
        ),
        link="https://jobs.example.com/automatai-llm",
    ),
    JobListing(
        title="AI Product Engineer",
        company="StartupX",
        description=(
            "Ship AI-powered features end-to-end from prototype to production. "
            "Need: Python, OpenAI API, prompt engineering, React basics, Supabase. "
            "0–2 years experience accepted. Passion for AI products essential."
        ),
        link="https://jobs.example.com/startupx-ai-product",
    ),
    JobListing(
        title="ML Engineer — NLP Focus",
        company="LangTech Solutions",
        description=(
            "Design NLP pipelines for text classification and abstractive summarization. "
            "Requirements: Python, scikit-learn, Hugging Face Transformers, SQL. "
            "Bonus: experience with OpenAI or Anthropic APIs, MLflow."
        ),
        link="https://jobs.example.com/langtech-ml-nlp",
    ),
    JobListing(
        title="Python Backend Developer",
        company="DataStream Inc",
        description=(
            "Develop REST APIs and data pipelines at scale. "
            "Stack: Python, FastAPI, PostgreSQL, Redis, Docker, Celery. "
            "AI/ML knowledge is a plus but not required."
        ),
        link="https://jobs.example.com/datastream-backend",
    ),
    JobListing(
        title="Data Scientist",
        company="AnalyticsPro",
        description=(
            "Statistical modeling and business insights from large datasets. "
            "Requirements: Python, pandas, matplotlib, SQL, R preferred. "
            "Supervised ML experience is a plus; no deep learning needed."
        ),
        link="https://jobs.example.com/analyticspro-ds",
    ),
    JobListing(
        title="AI Research Engineer",
        company="DeepMind Ventures",
        description=(
            "Conduct applied research on generative AI and multimodal models. "
            "Requirements: PhD or 3+ years industry experience, PyTorch, JAX, CUDA. "
            "Published papers in top ML venues strongly preferred."
        ),
        link="https://jobs.example.com/deepmind-research",
    ),
    JobListing(
        title="Robotics Software Engineer",
        company="MotionSys",
        description=(
            "Develop motion planning and control software for industrial robots. "
            "Requirements: Python, C++, ROS 2, computer vision (OpenCV). "
            "Strong math and linear algebra background required."
        ),
        link="https://jobs.example.com/motionsys-robotics",
    ),
]


async def get_jobs() -> list[JobListing]:
    """
    Returns available job listings.

    To swap in real scraping: replace this body with async HTTP calls to
    LinkedIn, HH.ru, or any job board. Keep the return type as list[JobListing].
    """
    return list(MOCK_JOBS)
