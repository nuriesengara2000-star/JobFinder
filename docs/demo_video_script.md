# Demo Video Script - JobFinder AI Agent

Target length: 3-5 minutes.

## 1. Introduction (0:00-0:30)

Hello, this is JobFinder AI Agent, my capstone project for the Generative AI Engineer course.

The problem is that junior and middle developers spend too much time manually searching for relevant jobs. Job platforms often return unrelated roles, such as senior, director, sales, or non-technical positions.

## 2. Solution (0:30-1:10)

JobFinder solves this problem by analyzing the user's resume, extracting skills and experience level, searching vacancies from multiple sources, filtering irrelevant results, and ranking jobs by fit score.

The goal is to help candidates find realistic job opportunities faster.

## 3. Live Demo (1:10-2:20)

Now I will show the application.

This is the Next.js frontend deployed on Vercel. I paste a resume into the input field and start the search.

The frontend sends the resume to the FastAPI backend deployed on Railway. The backend runs the autonomous ReAct agent. The agent uses custom tools for resume parsing, job search, and matching.

After processing, the system returns ranked vacancies with match score, company, source, description, and explanation.

## 4. API and Architecture (2:20-3:20)

The backend exposes two main endpoints: GET /health and POST /chat. The /chat endpoint uses Server-Sent Events for streaming-style frontend communication.

The architecture is: User -> Vercel Frontend -> Railway FastAPI Backend -> ReAct AI Agent -> Custom Tools -> External Services.

The custom tools include resume parsing, hh.kz search, LinkedIn search, RemoteOK search, We Work Remotely search, and job matching.

## 5. Technical Stack and Deployment (3:20-4:10)

The backend is built with Python, FastAPI, Pydantic, OpenAI API, SQLAlchemy, and Docker.

The frontend is built with Next.js, React, TypeScript, and Tailwind CSS.

The backend is deployed on Railway and the frontend is deployed on Vercel. The project also includes Dockerfile, docker-compose.yml, README, tests, proposal, architecture diagram, and deployment documentation.

## 6. Conclusion (4:10-4:30)

JobFinder is a working end-to-end AI product that demonstrates autonomous agent logic, custom tools, production API, frontend integration, and cloud deployment.

Future improvements include user accounts, PDF/DOCX resume upload, saved jobs, cover letter generation, PostgreSQL in production, and observability with LangSmith.
