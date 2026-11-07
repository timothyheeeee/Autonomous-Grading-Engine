# Autonomous Grading Engine: Enterprise Agentic Control Plane

**An open source multimodal AI orchestration engine designed to evaluate complex, asynchronous team contributions without mathematical hallucinations.**

Most LLM wrappers naively attempt to calculate metrics in a single probabilistic prompt, leading to hallucinations and failed audits. This repository implements a strict "Three Brain" architecture, utilizing Large Language Models purely as semantic parsers while offloading all numerical normalization to a deterministic Python and Pandas pipeline.

The result is a fully auditable, Human in the Loop (HITL) workflow that converts chaotic peer feedback into legally defensible, normalized percentage metrics.

***

## System Architecture: Deterministic Handoff

This system runs on a stateful LangGraph orchestration pipeline, executing three distinct nodes:

*   **Vision Extractor Node (Multimodal LLM):** Reads a rubric screenshot only when it shows real grading criteria and a scoring scale. A missing API key, a failed vision request, or an unrelated image stops the pipeline. The model does not invent criteria.
*   **Semantic Parser Node (Dynamic Entity Resolution):** Reads an unstructured peer-review CSV. The file must identify a student and contain task or feedback text. Inventory, weather, and employee tables are rejected. Accepted column names can vary, including `Student`, `Reviewee`, `Team Member`, `Tasks Completed`, and `Peer Feedback`.
*   **Deterministic Calculator Node (Pandas Data Engine):** The AI performs absolutely zero math. This isolated Python tool ingests the structured JSON and converts internal scores with a fixed maximum of 10: `percentage = (score / 10) * 100`. The uploaded rubric's original `scale_max` is kept as metadata and is never the denominator.

***

## Semantic input validation

A readable file is not treated as a valid upload. Before calculation, the pipeline checks three things:

*   The screenshot is a grading rubric, with at least one meaningful criterion and a scale from 1 to 100.
*   The CSV is peer-assessment data, not just a spreadsheet that happens to contain names or comments.
*   Each scoring action uses 0, 5, or 10, names a student from the CSV, uses a criterion from the extracted rubric, and is supported by that review.

If a score names the reviewer, or points at another student's row, it is moved to the review the text actually came from. Actions that still cannot be grounded are dropped. If nothing valid remains, the run stops and nothing is published. Percentages are saved only after you approve them.

The current prototype uses a simplified internal scoring system of 0, 5 and 10, converted to 0%, 50% and 100%. It does not reproduce every uploaded rubric's original numerical scoring bands. A rubric marked out of 100 and an internal score of 10 still produce 100%, not 10%. A rubric marked out of 5 and an internal score of 5 produce 50%, not 100%.

***

## Enterprise Grade Guardrails

Designed for production resilience and strict data observability:

*   **Traceable Execution:** Every score variation maps directly via correlation IDs back to the specific row in the raw CSV. The UI provides a step by step "Audit Trail" exposing the agent's reasoning.
*   **Human in the Loop Interrupts:** Utilizes LangGraph's interruption methodology. The pipeline pauses execution prior to database commits, requiring explicit admin authorization to finalize metrics.
*   **State Checkpointing:** Graph state is persisted via Redis and MemorySaver. If a runtime timeout occurs, the system resumes processing from the exact interrupted node.
*   **Risk Protection:** Implements input sanitization to strip prompt injection attempts from raw CSV uploads prior to LLM evaluation.
*   **Fail closed:** Invalid rubric images, unrelated CSVs, and ungrounded scores halt the graph before the calculator and the database.

***

## Strict Data Visualization Constraints

*   **No Raw Tallies:** The data pipeline is strictly prohibited from exposing raw counts. All evaluation metrics are mathematically normalized into percentages to ensure scale agnostic fairness.
*   **Explicit Labeling:** The Next.js dashboard utilizes Recharts to render metrics, with exact percentages explicitly labeled directly on the UI components for absolute transparency.

***

## Tech Stack

*   **AI Orchestration:** LangGraph, LangChain, Pydantic
*   **Core Logic:** Python, FastAPI, Pandas
*   **Frontend UI:** Next.js (TypeScript), Tailwind CSS, Framer Motion, Recharts
*   **State Persistence:** SQLite (Dev), Redis (State Checkpointing)
*   **Models:** OpenAI GPT-4o for rubric vision, GPT-4o-mini for semantic parsing

***

## Run

Set `OPENAI_API_KEY` in `backend/.env` before uploading. Restart the backend after changing it. Without that key, rubric verification stops and does not guess the criteria.

Backend:

```powershell
cd backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

Sample peer reviews: `backend/data/sample_peer_reviews.csv`

```bash
git clone https://github.com/timothyheeeee/Autonomous-Grading-Engine.git
```
