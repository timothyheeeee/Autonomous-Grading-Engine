# Autonomous Grading Engine: Enterprise Agentic Control Plane

**An open source multimodal AI orchestration engine designed to evaluate complex, asynchronous team contributions without mathematical hallucinations.**

Most LLM wrappers naively attempt to calculate metrics in a single probabilistic prompt, leading to hallucinations and failed audits. This repository implements a strict "Three Brain" architecture, utilizing Large Language Models purely as semantic parsers while offloading all numerical normalization to a deterministic Python and Pandas pipeline. 

The result is a fully auditable, Human in the Loop (HITL) workflow that converts chaotic peer feedback into legally defensible, normalized percentage metrics.

***

## System Architecture: Deterministic Handoff

This system runs on a stateful LangGraph orchestration pipeline, executing three distinct nodes:

*   **Vision Extractor Node (Multimodal LLM):** Ingests screenshot based academic rubrics. Translates complex visual matrices (categories, weights, and scoring rules) into a strictly typed Pydantic JSON schema.
*   **Semantic Parser Node (Dynamic Entity Resolution):** Ingests raw, unstructured peer review CSVs. Operates with zero hardcoded entities. The agent dynamically extracts unique team member names from unstructured text, cross references feedback against the visual rubric, and outputs a normalized JSON payload of evaluation actions.
*   **Deterministic Calculator Node (Pandas Data Engine):** The AI performs absolutely zero math. This isolated Python tool ingests the structured JSON, groups data by extracted entity, and calculates exact percentage normalizations.

***

## Enterprise Grade Guardrails

Designed for production resilience and strict data observability:

*   **Traceable Execution:** Every score variation maps directly via correlation IDs back to the specific row in the raw CSV. The UI provides a step by step "Audit Trail" exposing the agent's reasoning.
*   **Human in the Loop Interrupts:** Utilizes LangGraph's interruption methodology. The pipeline pauses execution prior to database commits, requiring explicit admin authorization to finalize metrics.
*   **State Checkpointing:** Graph state is persisted via Redis and MemorySaver. If a runtime timeout occurs, the system resumes processing from the exact interrupted node.
*   **Risk Protection:** Implements input sanitization to strip prompt injection attempts from raw CSV uploads prior to LLM evaluation.
*   **Cost Optimization:** Integrates an API circuit breaker that force halts execution after three failed entity extraction attempts, preventing infinite retry loops and API budget burn.

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
*   **Models:** OpenAI GPT-4o / Anthropic Claude 3.5 Sonnet

***

```bash
git clone [https://github.com/timothyheeeee/Autonomous-Grading-Engine.git](https://github.com/timothyheeeee/Autonomous-Grading-Engine.git)
