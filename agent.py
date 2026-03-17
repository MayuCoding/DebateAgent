from __future__ import annotations

from typing import Any

import instructor
from instructor import Mode
import logfire
from openai import OpenAI

from settings import Settings
from models import (
    DebateSide,
    OutputFormat,
    StudentSubmission,
    UnderstoodArguments,
    PointsResponse,
    RebuttalParagraphs,
    ReferencedParagraphs,
    EvidenceBasedResponse,
)
from decorators import span
from evidence import gather_evidence, GatheredEvidence


def build_client(settings: Settings) -> Any:
    client = OpenAI(base_url="https://api.mistral.ai/v1", api_key=settings.mistral_api_key)
    try:
        logfire.instrument_openai()
    except Exception:
        pass
    # Use JSON mode to avoid tool/function-calling issues with some providers
    return instructor.from_openai(client, mode=Mode.JSON)


def opposite_side(side: DebateSide) -> DebateSide:
    return DebateSide.con if side == DebateSide.pro else DebateSide.pro


@span("understand_arguments")
def understand_arguments(submission: StudentSubmission, client: Any, settings: Settings) -> UnderstoodArguments:
    system = (
        "You are a world-class debate analyst. Your job is to accurately understand the student's argument. "
        "Do not argue yet. Identify the core claims and key supporting points succinctly."
        "\nOutput format: return a JSON object with three keys: \"summary\", \"key_points\", and \"detected_claims\"."
        " Only emit the JSON object; do not wrap it in an additional top-level field."
    )
    msg_user = (
        "Motion: "
        + submission.motion
        + "\nStudent side: "
        + submission.student_side.value
        + "\nStudent argument:\n"
        + submission.argument_text
    )
    understood: UnderstoodArguments = client.chat.completions.create(
        model=settings.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": msg_user}],
        temperature=0.2,
        max_tokens=800,
        parallel_tool_calls=False,
        timeout=30.0,
        max_retries=2,
        response_model=UnderstoodArguments,
    )
    return understood


@span("generate_counter")
def generate_counter(
    submission: StudentSubmission,
    understood: UnderstoodArguments,
    client: Any,
    settings: Settings,
) -> PointsResponse | RebuttalParagraphs | ReferencedParagraphs:
    agent_side = opposite_side(submission.student_side)

    base_instructions = (
        """
        <persistence>
        You are a professional debate candidate familiar with teh Platonic ways of making arguments such that your arguments are well articulated and clear for participants to understand. You are to base all of your arguments from existing evidence which means you follow strictly the </response-process>
        </persistence>

        <response-process>
        Step 1: Using the websearch tool, search teh internet for articles and references regarding the motion but ones that reflect the side of argument you represent, for pro arguments teh references should support the argument, whereas for con arguments the references are to reflect the alternative side of the argument. Select teh top 10 arguments assceratining teh reference links are in fact from reliable sources rather than random social media posts.
        Step 2: After gathering teh top links from teh web search, read the contents of teh weblinks inorder to accurately reflect the gathered evidence in your response.
        Step 3: Formulate your response according to teh specified format, listing teh links gathered to support your evidence
        </response-process>

        <instructions>
        You are to understand an argument to a motion thoroughly, after which you are to gather evidence from the web and from teh gathered evidence formulate your response which should include the links.
        </instructions>

        <example-one>
        Motion: THBT the amount of homework per day should be limited 
        Side: Proposition
        Argument:
            This house believes that the amount of homework given to students each day should be limited 1 hour.
            
            
            To start, let me define some fo the terms in the motion. Homework refersdents, as doing homework is a responsibility of being  student. However, picture this, you are a student that has enrolled in lots ofg ex
            ents teachers give students to do at home. Per day means the time from the dissmissal from school to the start of the next school day. Limited means that the amount of homework given should not exceed a certain threshold, in our case, 1 hour.
            You may not understand why the amount of homerk should be limited to stuent
        References:
        -
        -
        -
        </example-one>
        
        
        """
        f"Debate motion: {submission.motion}\n"
        f"Student side: {submission.student_side.value}\n"
        f"Your side: {agent_side.value}\n"
        "First, ensure your counter-arguments directly address the student's actual claims summarized below.\n"
        f"Student summary: {understood.summary}\n"
        f"Key points: {understood.key_points}\n"
        f"Detected claims: {understood.detected_claims}\n"
        "Be concise, precise, and avoid strawmanning."
    )

    if submission.requested_format == OutputFormat.points:
        system = base_instructions + (
            "\nOutput format: POINTS. Return 3-6 strong counter-points.\n"
            "Each point may include a short support sentence in plain text.\n"
            "IMPORTANT: Return a JSON object only (no extra text) with a 'points' field."
        )
        pts: PointsResponse = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "system", "content": system}],
            temperature=0.1,
            max_tokens=800,
            parallel_tool_calls=False,
            timeout=30.0,
            max_retries=2,
            response_model=PointsResponse,
        )
        return pts

    if submission.requested_format == OutputFormat.rebuttal_paragraphs:
        system = base_instructions + (
            "\nOutput format: REBUTTAL_PARAGRAPHS. Provide 2-4 paragraphs.\n"
            "Each paragraph should rebut a specific student claim and explain why it is weak or incomplete.\n"
            "IMPORTANT: Return a JSON object only (no extra text) with a 'paragraphs' field."
        )
        paras: RebuttalParagraphs = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "system", "content": system}],
            temperature=0.1,
            max_tokens=900,
            parallel_tool_calls=False,
            timeout=30.0,
            max_retries=2,
            response_model=RebuttalParagraphs,
        )
        return paras

    # referenced_paragraphs - use evidence-first approach
    return generate_evidence_based_response(
        submission=submission,
        understood=understood,
        agent_side=agent_side,
        client=client,
        settings=settings,
    )


@span("generate_evidence_based_response")
def generate_evidence_based_response(
    submission: StudentSubmission,
    understood: UnderstoodArguments,
    agent_side: DebateSide,
    client: Any,
    settings: Settings,
) -> EvidenceBasedResponse:
    """
    Evidence-first approach for generating referenced paragraphs:
    1. Search web for the topic
    2. Gather real URLs with content
    3. Summarize each source
    4. Generate response ONLY from verified evidence
    """
    # Step 1-3: Gather and summarize evidence from web search
    evidence: GatheredEvidence = gather_evidence(
        motion=submission.motion,
        side=agent_side.value,
        tavily_api_key=settings.tavily_api_key,
        client=client,
        model=settings.model,
    )
    
    if not evidence.sources:
        raise ValueError(
            "No evidence sources found. Please set TAVILY_API_KEY in .env to enable web search."
        )
    
    # Format the gathered evidence for the LLM
    evidence_text = "\n\n".join([
        f"Source {i+1}:\n"
        f"URL: {s.url}\n"
        f"Title: {s.title}\n"
        f"Summary: {s.summary}\n"
        f"Key claims: {', '.join(s.key_claims)}\n"
        f"Relevance: {s.relevance_to_topic}"
        for i, s in enumerate(evidence.sources)
    ])
    
    available_urls = [s.url for s in evidence.sources]
    
    # Step 4: Generate response from verified evidence
    system = f"""You are a professional debate candidate. You must construct your argument ONLY from the verified evidence provided below.

Debate motion: {submission.motion}
Student side: {submission.student_side.value}
Your side: {agent_side.value}

Student's argument summary: {understood.summary}
Student's key points: {understood.key_points}
Student's detected claims: {understood.detected_claims}

<verified-evidence>
{evidence_text}
</verified-evidence>

<available-urls>
{chr(10).join(available_urls)}
</available-urls>

INSTRUCTIONS:
1. Write 2-4 paragraphs that counter the student's argument
2. Each paragraph MUST cite at least one source from the verified evidence above
3. You MUST ONLY use URLs from the <available-urls> list - do NOT invent or modify URLs
4. Each URL can only be used ONCE across all paragraphs (no URL reuse)
5. For each reference, include the specific claim from that source that supports your argument
6. Be concise, precise, and avoid strawmanning

IMPORTANT: Return a JSON object with a 'paragraphs' field. Each paragraph has 'text' and 'references' (array with 'url', 'title', 'supporting_claim')."""

    print(f"[generate] Building response from {len(evidence.sources)} verified sources...")
    
    response: EvidenceBasedResponse = client.chat.completions.create(
        model=settings.model,
        messages=[{"role": "system", "content": system}],
        temperature=0.1,
        max_tokens=1500,
        parallel_tool_calls=False,
        timeout=60.0,
        max_retries=3,
        response_model=EvidenceBasedResponse,
    )
    
    return response
