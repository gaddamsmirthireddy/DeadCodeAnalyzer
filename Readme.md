# CodeArchaeologist

> AI-powered Software Archaeology & Safe Code Deletion Intelligence

CodeArchaeologist is an AI software engineering platform that investigates whether code can be **safely deleted, preserved, quarantined, or reviewed**. Unlike traditional dead-code detectors, it combines static analysis, Git history, runtime evidence, test coverage, semantic reasoning, and RAG to produce explainable, evidence-backed recommendations.

---

## Why this project?

Traditional tools answer:

> "Is this function unused?"

CodeArchaeologist answers:

> "Should this code be removed, and what evidence supports that decision?"

The system is designed as an **AI investigation platform**, not a linter.

---

# MVP Input Method (Recommended)

**The application accepts an entire project folder as input.**

Users can either:

* Upload a ZIP of the repository
* Select a local project folder
* Clone a Git repository using its URL

The backend parses the complete codebase using Tree-sitter and Git history before starting the AI investigation.

**Future Version:** A VS Code extension can be built that sends the currently opened workspace to the FastAPI backend and displays recommendations directly inside the editor.

---

# Tech Stack

| Layer           | Technology                |
| --------------- | ------------------------- |
| Frontend        | React + TypeScript + Vite |
| Backend         | FastAPI                   |
| AI Workflow     | LangGraph                 |
| LLM Integration | LangChain                 |
| Static Analysis | Tree-sitter               |
| Database        | PostgreSQL + pgvector     |
| Cache           | Redis                     |
| Git Analysis    | GitPython                 |
| Simulation      | Docker                    |
| Deployment      | Docker Compose            |

---

# Project Structure

```text
codearchaeologist/
│
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── utils/
│   └── package.json
│
├── backend/
│   ├── api/                  # FastAPI routes
│   ├── analyzers/            # Static, Git, Runtime, Test analyzers
│   ├── ai/
│   │   ├── agents/           # LangGraph agents
│   │   ├── retrieval/        # RAG pipeline
│   │   └── prompts/
│   ├── simulation/           # Safe deletion sandbox
│   ├── database/
│   └── main.py
│
├── shared/
│   ├── schemas/
│   └── models/
│
├── docker/
├── docs/
├── tests/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# How It Works

```text
Project Folder / Git Repo
            │
            ▼
    Repository Parser
            │
            ▼
 Tree-sitter AST Analysis
            │
            ▼
 Candidate Dead Code
            │
            ▼
 ┌──────────────────────────┐
 │ LangGraph Investigation  │
 │ • Static Agent           │
 │ • Git Agent              │
 │ • Runtime Agent          │
 │ • Test Agent             │
 │ • Semantic Agent         │
 └─────────────┬────────────┘
               ▼
      RAG Evidence Retrieval
               ▼
      Deletion Simulation
               ▼
     Confidence & Recommendation
```

---

# AI Agents

### Static Analysis Agent

Detects imports, function calls, inheritance, routes, decorators, and dependency relationships.

### Git History Agent

Investigates:

* Who introduced the code
* Why it was added
* Refactoring history
* Previous deletion attempts

### Runtime Agent

Uses execution traces (future) to identify rarely executed or zombie code.

### Test Evidence Agent

Checks whether removing the code affects existing test coverage.

### Semantic Agent

Uses LLM reasoning to identify replacement implementations and infer the original purpose of the code.

### Judge Agent

Combines all evidence into a final recommendation.

---

# Features

* Evidence-based deletion confidence
* AI Code Archaeology timeline
* Semantic replacement detection
* Zombie code identification
* Evidence conflict detection
* Safe deletion simulation
* Explainable AI recommendations
* Historical deletion memory (RAG)

---

# API Overview

| Endpoint                    | Purpose                           |
| --------------------------- | --------------------------------- |
| `POST /projects/upload`     | Upload project ZIP                |
| `POST /projects/clone`      | Clone Git repository              |
| `POST /analysis/start`      | Start investigation               |
| `GET /analysis/{id}`        | Fetch analysis results            |
| `GET /recommendations/{id}` | Retrieve deletion recommendations |

---

# Development Roadmap

## Phase 1

* Upload repository
* Tree-sitter parsing
* Dependency graph
* Dead code candidates

## Phase 2

* Git history analysis
* PostgreSQL + pgvector
* RAG over commits & documentation

## Phase 3

* LangGraph multi-agent investigation
* Evidence conflict detection
* Confidence scoring

## Phase 4

* Docker deletion simulation
* Build & test validation
* React Flow visualization

## Phase 5

* VS Code Extension
* One-click project analysis
* Inline editor recommendations

---

# VS Code Extension (Future)

The extension is **not required for the MVP**.

Architecture:

```text
VS Code Workspace
        │
        ▼
Extension
        │
 REST API
        ▼
 FastAPI Backend
        │
 AI Investigation
        ▼
 Results returned to editor
```

The extension will simply act as a client, while all AI processing remains on the backend.

---

# Collaboration Guidelines

* Keep analyzers modular inside `backend/analyzers/`
* Each LangGraph agent should have its own prompt and logic
* Never allow LLMs to directly modify user code
* All recommendations must include supporting evidence
* Prefer deterministic analysis before LLM reasoning

---

# Core Principle

> **Delete code only when multiple independent sources of evidence agree.**

CodeArchaeologist is an AI decision-support platform that transforms code cleanup into an explainable software engineering investigation.
