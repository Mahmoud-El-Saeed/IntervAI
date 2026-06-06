<div align="center">

# IntervAI

**AI-Powered Technical Interview Platform**

[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1%2B-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq-LLM-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![pgvector](https://img.shields.io/badge/pgvector-Vector_DB-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8.0-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vite.dev)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real_Time-FFB300?style=flat-square&logo=websocket&logoColor=black)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<br/>

IntervAI is an end-to-end intelligent interview system that combines LangGraph orchestration, Retrieval-Augmented Generation (RAG), and real-time WebSocket communication to deliver adaptive technical interviews. The platform analyzes candidate resumes, aligns them against job descriptions, conducts live AI-driven interviews, and produces comprehensive performance reports.

<br/>

[Overview](#overview) &nbsp;&middot;&nbsp; [Architecture](#architecture) &nbsp;&middot;&nbsp; [System Design](#system-design) &nbsp;&middot;&nbsp; [Features](#features) &nbsp;&middot;&nbsp; [Getting Started](#getting-started) &nbsp;&middot;&nbsp; [Configuration](#configuration) &nbsp;&middot;&nbsp; [API Reference](#api-reference)

</div>

---

## Overview

IntervAI operates as a two-phase intelligent hiring assistant:

**Phase 1 -- Resume Analysis** ingests a candidate's resume (PDF or DOCX), extracts structured data using LLM-based parsing, aligns the candidate's skills against a target job description, validates consistency, performs market intelligence research via web search, fetches and summarizes GitHub project READMEs, and generates a preliminary analysis report with skill matching scores and learning roadmaps.

**Phase 2 -- Interactive Interview** initiates a real-time WebSocket-based conversation where an AI interviewer asks technical questions informed by the resume analysis, the candidate's GitHub projects, and RAG-retrieved context. The system features progressive hints, relevance-based routing, answer scoring with normalized metrics, and produces a final debrief report with strengths, focus areas, and a composite score.

The entire state of both workflows is persisted through LangGraph's PostgreSQL checkpointing, ensuring session continuity and fault tolerance.

---

## Architecture

```
                                    +--------------------+
                                    |     Frontend       |
                                    |   React + Vite     |
                                    |   TailwindCSS      |
                                    |   Zustand          |
                                    +--------+-----------+
                                             |
                          HTTP (REST)        |        WebSocket
                          +-------------------+------------------+
                          |                                      |
                 +--------v--------+                    +--------v--------+
                 |   FastAPI       |                    |   WebSocket     |
                 |   REST Routes   |                    |   Endpoint      |
                 |   Background    |                    |   Interview     |
                 |   Tasks         |                    |   Session       |
                 +--------+--------+                    +--------+--------+
                          |                                      |
                 +--------v--------------------------------------v--------+
                 |                       AI Service Layer                 |
                 |             LangGraph Workflows (Analysis + Interview) |
                 |             LLM Services (Groq)                        |
                 |             Tavily Web Search                          |
                 |             Google Generative AI Embeddings            |
                 +--------+----------------------------------------------+
                          |
                 +--------v--------+
                 |    PostgreSQL    |
                 |   + pgvector     |
                 |   Checkpoints    |
                 |   User Data      |
                 +-----------------+
```

---

## System Design

### Phase 1: Resume Analysis Pipeline

The analysis pipeline is implemented as a directed acyclic graph (DAG) in LangGraph. It executes the following nodes in sequence, with parallel execution for project processing:

| Node | Responsibility |
|------|---------------|
| `extract_cv` | Loads the resume document (PDF/DOCX), sends raw text to the LLM, and extracts structured fields: personal info, education, experience, extracted skills, and project links. |
| `align_job` | Compares extracted skills against the job description to produce categorized lists of matched skills, missing skills, and inferred job requirements. |
| `validate_alignment` | Cross-checks alignment consistency, normalizes the job title, identifies mismatches, and generates improvement recommendations. |
| `market_intelligence` | Generates targeted web search queries for the candidate's missing skills, executes Tavily searches, and collects market data. Runs in parallel with project pipelines. |
| `market_summary` | Synthesizes search results into structured insights: 2026 market trends, expected technical interview questions, and technology stack updates. |
| `project_pipeline` (subgraph) | For each GitHub project link found in the resume, fetches the raw README, generates embeddings for RAG, and produces a summary with tech stack, key features, and potential interview questions. Multiple projects are processed concurrently via LangGraph's `Send` primitive. |
| `finalize_analysis` | Assembles all outputs into a final analysis payload with overall score, verdict, learning roadmap, and skill breakdown. |

### Phase 2: Interactive Interview

The interview is implemented as a stateful LangGraph graph with interrupt-based human interaction, communicated over a persistent WebSocket connection:

| Node | Responsibility |
|------|---------------|
| `strategy_node` | Analyzes the resume analysis results and interview context to build an initial question strategy, prioritizing missing skills. |
| `question_generator_node` | Generates a single technical question per turn, using RAG-retrieved context from the candidate's resume and projects to produce specific or conceptual questions. |
| `human_input_node` | Pauses graph execution using LangGraph's `interrupt` to wait for the candidate's answer via WebSocket. |
| `analyzer_node` | Evaluates the answer for technical accuracy, completeness, and relevance. Cross-references claims against the candidate's resume using RAG retrieval. Flags potential exaggerations or contradictions. |
| `hint_node` | Provides progressive hints (up to 2 per question) with increasing specificity. Falls back to deterministic hints on LLM failures or rate limits. |
| `summarize_node` | Every 3 turns, compresses conversation history to manage context window size and cost. |
| `evaluator_node` | Scores the answer on a 0-10 scale across technical accuracy, completeness, clarity, and depth. Provides actionable feedback. |
| `generate_final_report_node` | Produces the final interview debrief with overall assessment, recommendation, strengths, focus areas, and normalized average score. |

**Routing Logic:**
- After analysis, low-relevance answers (score below 70) are routed to the hint node instead of the evaluator.
- After evaluation, the graph routes to the final report if all questions have been asked, or to the summarizer every 3rd turn, or directly to the next question generator.
- After hints, the graph routes back to human input for a refined answer unless the maximum hint count is reached.

---

## Features

### Resume Processing
- **Multi-format support**: Ingests PDF and DOCX resumes via async file upload
- **LLM-powered extraction**: Extracts structured data (personal info, education, experience, skills, project links) using Groq's LLM with JSON output parsing
- **Job alignment engine**: Maps candidate skills to job requirements, identifies matched and missing skills
- **Consistency validation**: Detects profile mismatches, normalizes job titles, and produces actionable recommendations

### Market Intelligence
- **Automated web research**: Generates targeted search queries for missing skills using Tavily search API
- **Trend analysis**: Synthesizes market data into structured insights including 2026 trends and expected interview questions

### Project Analysis
- **GitHub README fetching**: Automatically discovers and fetches raw README files from candidate's GitHub project links
- **Concurrent processing**: Processes multiple project READMEs in parallel using LangGraph's fan-out pattern
- **RAG ingestion**: Chunks README content, generates embeddings via Google Generative AI, and stores them in pgvector for later retrieval
- **Project summarization**: Extracts tech stack, key features, and generates potential interview questions from each project

### Interactive Interview
- **Real-time WebSocket communication**: Persistent bidirectional connection with automatic reconnection and message queuing
- **RAG-enhanced questioning**: Questions are informed by vector similarity search against the candidate's resume and project embeddings
- **Adaptive difficulty**: Questions target missing skills first, then progress through matched skills with increasing complexity
- **Progressive hint system**: Up to 2 hints per question with increasing specificity; LLM-generated with deterministic fallback
- **Conversation compression**: Automatic history summarization every 3 turns to maintain context efficiency
- **Fact-checking**: Cross-references candidate answers against their own resume to detect exaggerations or contradictions

### Scoring and Reporting
- **Normalized scoring**: All answers scored on a 0-100 normalized scale with per-question and cumulative tracking
- **Hint penalty awareness**: Score context accounts for hint usage in evaluation
- **Final debrief report**: Comprehensive report with strengths, focus areas, recommendation, and composite score
- **Persistent state**: Interview and analysis state persisted through LangGraph PostgreSQL checkpointing for fault tolerance and session recovery

### Authentication and Security
- **JWT authentication**: Access tokens and refresh tokens with configurable expiration
- **Argon2 password hashing**: Secure password storage via pwdlib
- **Protected routes**: Role-based route protection on both frontend and backend

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | FastAPI (Python 3.13+) |
| **AI Orchestration** | LangGraph with PostgreSQL checkpointing |
| **LLM Provider** | Groq (llama-3.3-70b-versatile) |
| **Web Search** | Tavily Search API |
| **Embeddings** | Google Generative AI (text-embedding-004) |
| **Vector Store** | pgvector (PostgreSQL extension) |
| **Database** | PostgreSQL with SQLAlchemy ORM |
| **Migrations** | Alembic |
| **Frontend Framework** | React 19 with Vite 8 |
| **State Management** | Zustand |
| **Styling** | TailwindCSS with custom dark theme |
| **Real-time Communication** | WebSocket with automatic reconnection |
| **Authentication** | JWT (access + refresh tokens), Argon2 hashing |
| **Document Parsing** | PyMuPDF, PyPDF, docx2txt |
| **Text Splitting** | LangChain RecursiveCharacterTextSplitter |
| **HTTP Client** | httpx (async) with retry logic via tenacity |

---

## Project Structure

```
IntervAI/
|
|-- backend/
|   |-- main.py                          # FastAPI application entry point
|   |-- pyproject.toml                   # Python dependencies (uv)
|   |-- alembic.ini                      # Alembic migration configuration
|   |-- alembic/                         # Database migrations
|   |   |-- versions/                    # Migration scripts
|   |
|   |-- app/
|       |-- database.py                  # SQLAlchemy engine and session
|       |
|       |-- ai/                          # LangGraph workflows and AI logic
|       |   |-- graph.py                 # Graph builders (analysis + interview)
|       |   |-- state.py                 # TypedDict state definitions
|       |   |-- schemas.py               # Pydantic models for LLM outputs
|       |   |-- prompts.py               # System prompts for all AI nodes
|       |   |-- constants.py             # Configuration constants and thresholds
|       |   |-- services.py              # LLM and search service factories
|       |   |-- helpers.py               # Utility functions (scoring, embedding)
|       |   |-- exceptions.py            # Custom exception classes
|       |   |-- nodes.py                 # Re-exports for AI module
|       |   |-- nodes_analysis.py        # Resume analysis graph nodes
|       |   |-- nodes_interview.py       # Interview session graph nodes
|       |
|       |-- core/                        # Core infrastructure
|       |   |-- config.py                # Settings (pydantic-settings)
|       |   |-- security.py              # JWT and password utilities
|       |   |-- loader.py                # Document text extraction
|       |   |-- embedder.py              # Google Generative AI embeddings
|       |   |-- retrieval.py             # RAG vector similarity search
|       |   |-- analysis_logging.py      # Structured logging for analysis
|       |
|       |-- controller/                  # File handling controllers
|       |   |-- file_controller.py       # Upload and file management
|       |
|       |-- db/                          # Database CRUD operations
|       |   |-- user_crud.py
|       |   |-- interview_crud.py
|       |   |-- interview_analysis_crud.py
|       |   |-- resume_curd.py
|       |   |-- refresh_token_crud.py
|       |   |-- document_embedding_crud.py
|       |
|       |-- enums/                       # Application enumerations
|       |   |-- interview_status.py
|       |   |-- file_response.py
|       |
|       |-- models/                      # SQLAlchemy ORM models
|       |   |-- user.py
|       |   |-- resume.py
|       |   |-- interview.py
|       |   |-- interview_question.py
|       |   |-- interview_answer.py
|       |   |-- interview_analysis.py
|       |   |-- document_embedding.py
|       |   |-- refresh_token.py
|       |
|       |-- routes/                      # FastAPI route handlers
|       |   |-- auth.py                  # Login, register, refresh
|       |   |-- interview.py            # REST + WebSocket endpoints
|       |   |-- resume.py               # Resume upload and listing
|       |   |-- dependencies.py          # Auth dependency injection
|       |
|       |-- schemas/                     # Pydantic request/response schemas
|       |   |-- user.py
|       |   |-- interview.py
|       |   |-- interview_question.py
|       |   |-- interview_answer.py
|       |   |-- resume.py
|       |   |-- tokens.py
|       |
|       |-- services/                    # Business logic services
|           |-- auth.py
|           |-- user.py
|           |-- interview.py
|           |-- resume.py
|           |-- ai_service.py            # LangGraph orchestration service
|
|-- frontend/
|   |-- package.json                     # Node.js dependencies
|   |-- vite.config.js                   # Vite build configuration
|   |-- tailwind.config.js               # TailwindCSS with custom dark theme
|   |-- postcss.config.js
|   |-- index.html
|   |
|   |-- src/
|       |-- main.jsx                     # React entry point
|       |-- App.jsx                      # Root component
|       |-- App.css
|       |-- index.css                    # Global styles and Tailwind layers
|       |
|       |-- app/
|       |   |-- router.jsx               # React Router configuration
|       |
|       |-- components/
|       |   |-- auth/
|       |   |   |-- ProtectedRoute.jsx    # Auth guard component
|       |   |-- layout/
|       |   |   |-- AppShell.jsx          # Sidebar navigation layout
|       |   |-- resume/
|       |   |   |-- SelectResumeModal.jsx
|       |   |-- ui/
|       |       |-- Button.jsx
|       |       |-- Input.jsx
|       |       |-- StatusBadge.jsx
|       |
|       |-- pages/
|       |   |-- LoginPage.jsx
|       |   |-- RegisterPage.jsx
|       |   |-- DashboardPage.jsx         # Interview history and session creation
|       |   |-- LiveInterviewPage.jsx    # Real-time interview interface
|       |   |-- AnalysisReportPage.jsx   # Final report display
|       |   |-- SettingsPage.jsx
|       |   |-- NotFoundPage.jsx
|       |
|       |-- lib/
|       |   |-- api/
|       |   |   |-- client.js            # Axios instance with auth interceptors
|       |   |   |-- authApi.js
|       |   |   |-- interviewApi.js
|       |   |   |-- resumeApi.js
|       |   |   |-- orchestrator.js       # Multi-step interview initiation
|       |   |-- ws/
|       |   |   |-- interviewSocket.js   # WebSocket client with reconnection
|       |   |-- config.js
|       |   |-- storage.js               # Token persistence
|       |   |-- utils.js
|       |
|       |-- store/
|           |-- authStore.js             # Authentication state
|           |-- interviewStore.js        # Interview session state
|
|-- docker/
|   |-- docker-compose.yml               # PostgreSQL + pgvector
|   |-- .env.example
|
|-- LICENSE                               # MIT License
|-- README.md
```

---

## Getting Started

### Prerequisites

- Python 3.13 or later
- Node.js 18 or later
- PostgreSQL with the pgvector extension
- A Groq API key ([groq.com](https://groq.com))
- A Tavily API key ([tavily.com](https://tavily.com))
- A Google AI API key for embeddings ([makersuite.google.com](https://makersuite.google.com))
- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

### Database Setup

Start a PostgreSQL instance with pgvector using Docker Compose:

```bash
cd docker
cp .env.example .env
# Edit .env with your database credentials
docker compose up -d
```

Then run database migrations:

```bash
cd ../backend
alembic upgrade head
```

### Backend Setup

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys and database URI
uv sync
uv run fastapi dev main.py
```

The backend API will be available at `http://localhost:8000`.

### Frontend Setup

```bash
cd frontend
cp .env.example .env
# Edit .env with your backend API URL
npm install
npm run dev
```

The frontend application will be available at `http://localhost:5173`.

---

## Configuration

All configuration is managed through environment variables. Copy the `.env.example` files and fill in your credentials.

### Backend Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM inference | `gsk_...` |
| `TAVILY_API_KEY` | Tavily API key for web search | `tvly-...` |
| `EMBEDDING_PROVIDER` | Embedding service provider | `google` |
| `EMBEDDING_MODEL` | Embedding model name | `text-embedding-004` |
| `EMBEDDING_DIMENSION` | Embedding vector dimension | `1024` |
| `EMBEDDING_API_KEY` | API key for embedding service | `AIza...` |
| `DATABASE_URI` | PostgreSQL connection string (with psyco) | `postgresql+psycopg://...` |
| `DATABASE_URI_NO_PSYCOG` | PostgreSQL connection string (without psyco, for LangGraph) | `postgresql://...` |
| `JWT_SECRET_KEY` | Secret key for JWT token signing | `your-secret-key` |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime in days | `7` |
| `FILE_ALLOWED_TYPES` | Accepted resume MIME types | `["application/pdf", ...]` |
| `FILE_ALLOWED_SIZE_MB` | Maximum upload size in megabytes | `10` |
| `FILE_UPLOAD_DIR` | Directory for uploaded resumes | `Files/users` |

### AI Configuration Constants

These are defined in `backend/app/ai/constants.py` and can be tuned for different interview behaviors:

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_QUESTIONS` | 5 | Maximum number of interview questions per session |
| `MAX_HINT_COUNT` | 2 | Maximum hints per question before skipping |
| `RELEVANCE_HINT_THRESHOLD` | 70 | Minimum relevance score to bypass hints (0-100) |
| `MAX_RESUME_LENGTH` | 12000 | Maximum resume text length sent to LLM (characters) |
| `MAX_JD_LENGTH` | 6000 | Maximum job description length (characters) |
| `MAX_SEARCH_RESULTS` | 3 | Maximum Tavily search results per query |
| `LLM_SMART_MODEL` | `llama-3.3-70b-versatile` | Model used for analysis and evaluation nodes |
| `LLM_FAST_MODEL` | `llama-3.3-70b-versatile` | Model used for generation and hint nodes |

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register a new user account |
| `POST` | `/auth/login` | Authenticate and receive JWT tokens |
| `POST` | `/auth/refresh` | Refresh an expired access token |

### Resumes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/resume` | List all uploaded resumes |
| `POST` | `/resume/upload` | Upload a resume file (PDF/DOCX) |

### Interviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/interview` | Create a new interview session |
| `GET` | `/interview` | List interview history |
| `GET` | `/interview/{id}` | Get full interview details |
| `POST` | `/interview/{id}/analysis` | Trigger resume analysis (background task) |
| `GET` | `/interview/{id}/status` | Poll analysis completion status |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/interview/{id}?token=...` | Real-time interview session |

**WebSocket Message Types:**

| Type | Direction | Description |
|------|-----------|-------------|
| `answer` | Client to Server | Submit an answer to the current question |
| `ping` | Client to Server | Keep-alive heartbeat |
| `state` | Client to Server | Request current session state |
| `session_started` | Server to Client | Initial session payload with first question |
| `turn_result` | Server to Client | Result after answer processing (question/feedback/hint) |
| `hint_provided` | Server to Client | Progressive hint delivery |
| `session_completed` | Server to Client | Final report and session termination |
| `pong` | Server to Client | Ping acknowledgment |
| `error` | Server to Client | Error notification |

---

## How It Works

**1. User Registration and Resume Upload**

A candidate creates an account and uploads their resume. The system stores the file and extracts the raw text content.

**2. Session Creation and Resume Analysis**

The user specifies a target job title and description. The system creates an interview record and triggers a background analysis task. The LangGraph analysis pipeline executes: CV extraction, job alignment, validation, market research, and project README analysis (all running concurrently where possible). Results are persisted to the database.

**3. Interactive Interview**

Once analysis completes, the user enters a live interview session via WebSocket. The LangGraph interview graph initializes with the analysis context, generates a strategy, and produces the first question targeting the candidate's weakest skills. The candidate responds, and the graph routes through analysis, hint evaluation, and scoring nodes.

**4. RAG-Enhanced Context**

During both question generation and answer analysis, the system retrieves relevant chunks from the candidate's resume and project README embeddings stored in pgvector. This ensures questions are grounded in the candidate's actual experience and that answers can be fact-checked against stated qualifications.

**5. Report Generation**

After all questions are exhausted, the final report node produces a comprehensive assessment. This report is persisted alongside the resume analysis, giving the candidate a complete view of their technical readiness for the target role.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 Mahmoud El Saeed Mohammed
