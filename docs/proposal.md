# JobFinder AI Agent - Project Proposal

## 1. Problem

Junior and middle IT specialists often spend too much time searching for relevant vacancies. Job platforms return many unrelated results, and candidates have to manually compare each vacancy with their resume, skills, experience level, and career goals.

This is especially difficult for students and junior AI/backend developers because many job platforms mix junior, senior, management, sales, legal, and non-technical roles in the same search results.

## 2. Target User

The target users are:

- junior and middle IT specialists;
- students looking for internships or entry-level jobs;
- AI, GenAI, backend, Python, and full-stack developers;
- candidates who want to understand which jobs match their resume and what skills they are missing.

## 3. Current Solution Without the Product

Today, candidates usually search manually on hh.kz, LinkedIn, RemoteOK, We Work Remotely, and similar platforms. They open many vacancies one by one, read the requirements, compare them with their resume, and decide whether to apply.

This process is slow, repetitive, and often inaccurate because users may miss relevant roles or apply to jobs that do not match their level.

## 4. Proposed Solution

JobFinder AI Agent is an AI-powered job search assistant. The user pastes a resume into the web interface, and the system:

1. analyzes the resume;
2. extracts skills, experience level, and target role;
3. searches vacancies from multiple sources;
4. filters irrelevant jobs;
5. ranks vacancies by fit score;
6. explains why each job matches the candidate.

The final result is a ranked list of relevant job recommendations with match explanations.

## 5. Agent Logic

The project uses an autonomous ReAct-style agent. The agent follows a loop of:

- Thought;
- Action;
- Observation;
- Final Answer.

The agent is not a simple prompt-response chatbot. It can decide which tool to use next, such as resume parsing, job searching, or vacancy matching. This makes the system closer to a real AI assistant that can reason about the next step.

## 6. Custom Tools

The project includes custom tools created specifically for the job search domain:

- Resume Parser - extracts skills, experience level, location, and target role from the user's resume.
- HH Search Tool - searches vacancies from hh.kz.
- LinkedIn Search Tool - searches LinkedIn-style job results.
- RemoteOK Search Tool - searches remote tech jobs.
- We Work Remotely Search Tool - searches remote vacancies.
- Job Matching Tool - ranks jobs by relevance and filters unrelated roles.

These tools are domain-specific and were implemented as part of the project, so they satisfy the capstone requirement for custom tools.

## 7. Architecture

The system architecture is:

User -> Vercel Frontend -> Railway FastAPI Backend -> ReAct AI Agent -> Custom Tools -> External Services

Main components:

- Next.js frontend deployed on Vercel;
- FastAPI backend deployed on Railway;
- ReAct agent for autonomous reasoning;
- custom job-search tools;
- OpenAI API for LLM reasoning;
- optional database layer for users, saved jobs, and applications.

## 8. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| AI Agent | ReAct-style autonomous agent |
| LLM | OpenAI API |
| Database Layer | SQLAlchemy, Alembic |
| Deployment | Railway, Vercel |
| Containerization | Docker, Docker Compose |
| Testing | Pytest, FastAPI TestClient |

## 9. Why This Stack Was Chosen

FastAPI was chosen because it is lightweight, fast, and suitable for production-ready AI APIs. It also supports Pydantic validation and streaming responses.

Next.js was chosen because it provides a modern frontend experience and is easy to deploy on Vercel.

Railway was selected for backend deployment because it supports Python services, environment variables, health checks, and public URLs.

Vercel was selected for frontend deployment because it is optimized for Next.js applications.

Docker was added to make the application easier to run locally and to satisfy production packaging requirements.

## 10. Production Features

The project includes:

- public FastAPI backend;
- public Next.js frontend;
- Pydantic request validation;
- streaming response endpoint;
- request logging;
- basic in-memory rate limiting;
- CORS configuration;
- Dockerfile;
- docker-compose.yml;
- deployment configuration for Railway and Vercel.

## 11. Expected Result

The final application provides a public web interface where users can paste their resume and receive AI-ranked job recommendations with match scores and explanations.

## 12. Limitations

Current limitations:

- search quality depends on available public job data;
- some job platforms may limit scraping or return incomplete data;
- the current database layer is prepared but not fully used in the frontend workflow;
- the agent streams final structured events, but token-by-token LLM streaming can be improved later.

## 13. Future Improvements

Planned improvements:

- add user authentication;
- save job search history;
- allow users to upload PDF/DOCX resumes from the web UI;
- add cover letter generation;
- add observability with LangSmith;
- add a full RAG layer for resume improvement and interview preparation;
- add PostgreSQL in production;
- improve prompt-injection protection;
- add more evaluation test cases.
