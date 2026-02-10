# Assignment 01 · Debate Opponent (Pydantic + Instructor + Mistral + Logfire)

Instructor reference for running, assessing, and extending the assignment where students build a debate opponent that argues the opposite side, understands the student's claims first, and outputs in one of three formats.

## Learning Objectives

- **Pydantic modeling**: Enums, structured schemas, URL validation.
- **Instructor usage**: Coerce LLM output to a target schema (`response_model`).
- **OpenAI-compatible client to Mistral**: Route via `base_url`.
- **Observability**: Logfire spans and OpenAI client instrumentation.
- **Prompting discipline**: Separate “understand” stage from “generate counter”.

## Core Requirements

- **Opposite side selection**: If student is `pro`, agent argues `con`, and vice versa.
- **Two-stage flow**:
  - Stage 1: Accurately summarize the student's argument (`UnderstoodArguments`).
  - Stage 2: Generate a counter-argument grounded in Stage 1.
- **Output formats** (chosen by the student via CLI):
  - `points`: `PointsResponse` → 3–6 strong bullet points with optional short support text.
  - `rebuttal_paragraphs`: `RebuttalParagraphs` → 2–4 paragraphs rebutting specific claims.
  - `referenced_paragraphs`: `ReferencedParagraphs` → 2–4 paragraphs with a list of references per paragraph; URLs validated with `AnyUrl`.
- **LLM/Tools**: Mistral via OpenAI SDK + Instructor; Pydantic for schemas; Logfire for spans + instrumentation.

## Repository Structure (solution scaffold)

- `settings.py` — `BaseSettings` (`MISTRAL_API_KEY`, `MISTRAL_MODEL`, `LOGFIRE_TOKEN`, `ENVIRONMENT`) and Logfire init.
- `models.py` — `DebateSide`, `OutputFormat`, `StudentSubmission`, `UnderstoodArguments`,
  `PointsResponse`, `RebuttalParagraphs`, `ReferencedParagraphs` (with `Reference.url: AnyUrl`).
- `decorators.py` — `@span(name)` decorator for Logfire spans.
- `agent.py` — `build_client()`, `understand_arguments()`, `generate_counter()` with Instructor `response_model`.
- `main.py` — CLI wrapper; passes Logfire span attributes (motion, sides, format).
- `.env.example`, `requirements.txt`.

## Setup

1. Create a virtual environment and install deps:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` → `.env` and set values:
   - `MISTRAL_API_KEY` (required)
   - `MISTRAL_MODEL` (default: `mistral-small-latest`)
   - `LOGFIRE_TOKEN` (optional)
   - `ENVIRONMENT` (default: `dev`)

## Running Examples

- Points format:
  
  ```bash
  python main.py --motion "Should I stay up late with a coffee to finish three assignments due at midnight, being that it's only 7pm" --side con --format points --argument "I should not, seems bad for your health"
  ```
  
- Rebuttal paragraphs:
  
  ```bash
  python main.py --motion "Ban single-use plastics" --side con --format rebuttal_paragraphs --argument_file my_argument.txt
  ```
  
- Referenced paragraphs (includes URLs):
  
  ```bash
  python main.py --motion "Adopt nuclear energy aggressively" --side pro --format referenced_paragraphs --argument "Nuclear is too risky and slow to deploy."
  ```

## Assessment Guide (Rubric)

- **Understanding accuracy (30%)** — `UnderstoodArguments` faithfully captures claims and key points (no strawmanning).
- **Counter-argument strength (30%)** — Logical rigor, relevance to the student's claims, avoids fallacies.
- **Format adherence (20%)** — Matches the requested format and schema; Instructor validation passes.
- **References quality (15%)** — For referenced output: credible sources, appropriate to claims. Note: `AnyUrl` validates format, not credibility or 200-status; spot-check links.
- **Code quality (5%)** — Clear structure, sensible defaults, minimal repetition, readable prompts.

## Instructor Workflow

- Provide the motion and the student's side/argument, pick a format, and run the CLI.
- Inspect Logfire traces to review:
  - `understand_arguments` span with attributes (motion, student_side).
  - `generate_counter` span with attributes (motion, student_side, agent_side, format).
  - OpenAI/Mistral instrumentation for request/response.
- For referenced outputs, manually open a sample of URLs to verify they support the claims.

## Troubleshooting

- Missing API key → set `MISTRAL_API_KEY` in `.env` or environment.
- Validation errors from Instructor → the model output didn’t match the schema; it will auto-retry. If persistent, reduce `temperature` in `agent.py` or tighten instructions.
- Low-quality/irrelevant references → refine the prompt in `generate_counter()` to emphasize authoritative domains.

## Extension Ideas

- Add unit tests for schema validation and prompt consistency.
- Allow multi-turn refinement (e.g., ask clarifying questions before countering).
- Add a "strength meter" or self-eval pass to score argument quality.
- Persist runs as JSONL with timestamps and spans for grading artifacts.
