"""LangGraph nodes for interview workflow."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import interrupt

from .constants import MAX_QUESTIONS, MAX_RESUME_LENGTH, MAX_JD_LENGTH, MAX_HINT_COUNT
from .exceptions import InterviewError, LLMError
from .helpers import log_progress, build_msg
from .helpers import normalize_interview_score
from .prompts import (
    SYSTEM_STRATEGY,
    SYSTEM_QUESTION_GENERATOR,
    SYSTEM_ANALYZER,
    SYSTEM_HINT,
    SYSTEM_EVALUATOR,
    SYSTEM_FINAL_REPORT,
)
from .schemas import (
    NextQuestion,
    AnalysisResult,
    EvaluationResult,
    FinalReportResult,
)
from .services import (
    get_strategy_service,
    get_question_service,
    get_analysis_service,
    get_hint_service,
    get_evaluation_service,
    get_report_service,
    invoke_llm_chain,
)
from .state import InterviewSessionState


_HINT_RATE_LIMIT_RETRY_DELAY_SECONDS = 1.5


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "rate_limit_exceeded" in message


def _build_fallback_hint(current_question: str, expected_answer: str, hint_counter: int) -> str:
    question = current_question.strip().rstrip("?")
    expected = expected_answer.strip()

    if hint_counter <= 0:
        prefix = "Start with the core idea."
    elif hint_counter == 1:
        prefix = "Add the key implementation detail."
    else:
        prefix = "Close in on the exact mechanism."

    if expected:
        expected_summary = expected
        if len(expected_summary) > 180:
            expected_summary = expected_summary[:177].rstrip() + "..."
        if question:
            return f"{prefix} Explain how {question.lower()} connects to: {expected_summary}"
        return f"{prefix} Make sure your answer covers: {expected_summary}"

    if question:
        return f"{prefix} Focus on why {question.lower()} matters and mention one concrete trade-off."

    return f"{prefix} Focus on the main concept, the trade-off, and one concrete example."


async def strategy_node(state: InterviewSessionState) -> dict[str, Any]:
    """Build initial interview strategy."""
    log_progress("strategy_node", "Building initial interview strategy")

    text = state.get("resume_text", "")
    jd = state.get("job_description", "")
    job_title = state.get("job_title", "")
    job_requirements = list(state.get("job_requirements", []))
    missing_skills = list(state.get("missing_skills", []))
    matched_skills = list(state.get("matched_skills", []))

    # Extract potential project questions from state if available
    project_summaries = state.get("project_summaries", {})
    project_questions = []
    for project_name, summary in project_summaries.items():
        if isinstance(summary, dict) and "potential_interview_questions" in summary:
            project_questions.extend(summary["potential_interview_questions"])

    # Keep project questions supplementary only
    project_questions = project_questions[:2]

    parser = JsonOutputParser(pydantic_object=NextQuestion)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_STRATEGY + "\n{format_instructions}"),
            (
                "human",
                "Build a one-question strategy for the first interview question.\n\n"
                "=== JOB CONTEXT ===\n"
                "Job Title: {job_title}\n"
                "Job Requirements: {job_requirements}\n"
                "Missing Skills: {missing_skills}\n"
                "Matched Skills: {matched_skills}\n\n"
                "=== CANDIDATE BACKGROUND ===\n"
                "Resume:\n{resume}\n\n"
                "Job Description:\n{jd}\n\n"
                "=== PROJECT QUESTIONS (SECONDARY ONLY) ===\n"
                "{project_questions}\n\n"
                "FIRST QUESTION MUST TEST A MISSING SKILL FROM THE JOB REQUIREMENTS",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "job_title": job_title,
                "job_requirements": json.dumps(job_requirements, ensure_ascii=False),
                "missing_skills": json.dumps(missing_skills, ensure_ascii=False),
                "matched_skills": json.dumps(matched_skills, ensure_ascii=False),
                "resume": text[:MAX_RESUME_LENGTH],
                "jd": jd[:MAX_JD_LENGTH],
                "project_questions": json.dumps(project_questions, ensure_ascii=False),
            },
            get_strategy_service(),
        )

        return {
            "strategy": out,
            "status": "interview_started",
            "progress_message": "Interview strategy prepared",
        }
    except Exception as e:
        log_progress("strategy_node", f"Strategy failed: {e}")
        raise InterviewError(f"Strategy node failed: {e}") from e


async def question_generator_node(state: InterviewSessionState) -> dict[str, Any]:
    """Generate the next interview question."""
    log_progress("question_generator_node", "Generating next interview question")

    asked = state.get("asked_questions", [])
    answers = state.get("answers", [])
    analysis = state.get("analysis", [])
    strategy = state.get("strategy", {})
    question_count = int(state.get("total_questions_asked", state.get("question_count", 0)) or 0)

    if question_count >= MAX_QUESTIONS:
        return {
            "chat_history": [build_msg("ai", "Thanks. We have completed all interview questions.")],
            "status": "interview_completed",
            "progress_message": "Interview completed",
        }

    job_title = state.get("job_title", "")
    job_requirements = list(state.get("job_requirements", []))
    missing_skills = list(state.get("missing_skills", []))
    matched_skills = list(state.get("matched_skills", []))

    # Get project questions for context
    project_summaries = state.get("project_summaries", {})
    project_questions = []
    project_tech_stacks: dict[str, Any] = {}
    for project_name, summary in project_summaries.items():
        if not isinstance(summary, dict):
            continue

        if "potential_interview_questions" in summary:
            project_questions.extend(summary["potential_interview_questions"])

        if "tech_stack" in summary:
            project_tech_stacks[project_name] = summary["tech_stack"]
    
    # Limit to top 2 so projects remain secondary
    project_questions = project_questions[:2]

    parser = JsonOutputParser(pydantic_object=NextQuestion)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_QUESTION_GENERATOR + "\n{format_instructions}"),
            (
                "human",
                "question_count={question_count}, max={max_q}.\n\n"
                "=== JOB CONTEXT (PRIMARY SOURCE FOR QUESTIONS) ===\n"
                "Job Title: {job_title}\n"
                "Job Requirements: {job_requirements}\n"
                "Missing Skills (TEST THESE FIRST): {missing_skills}\n"
                "Matched Skills (VERIFY DEPTH): {matched_skills}\n\n"
                "=== CANDIDATE PROJECTS (SECONDARY ONLY) ===\n"
                "Project Tech Stacks: {project_tech_stacks}\n"
                "Available Project Questions: {project_questions}\n\n"
                "=== INTERVIEW PROGRESS ===\n"
                "Strategy: {strategy}\n"
                "Asked: {asked}\n"
                "Answers: {answers}\n"
                "Analyses: {analysis}\n\n"
                "REMEMBER: 80% of questions must test job requirements. Max one project question every five questions.",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "question_count": question_count,
                "max_q": MAX_QUESTIONS,
                "job_title": job_title,
                "job_requirements": json.dumps(job_requirements, ensure_ascii=False),
                "missing_skills": json.dumps(missing_skills, ensure_ascii=False),
                "matched_skills": json.dumps(matched_skills, ensure_ascii=False),
                "project_tech_stacks": json.dumps(project_tech_stacks, ensure_ascii=False),
                "project_questions": json.dumps(project_questions, ensure_ascii=False),
                "strategy": json.dumps(strategy, ensure_ascii=False),
                "asked": json.dumps(asked[-5:], ensure_ascii=False),
                "answers": json.dumps(answers[-5:], ensure_ascii=False),
                "analysis": json.dumps(analysis[-3:], ensure_ascii=False),
            },
            get_question_service(),
        )

        question = out["question"].strip()
        expected_answer = out.get("expected_answer", "").strip()

        log_progress("question_generator_node", f"Question {question_count + 1} generated")
        return {
            "current_question": question,
            "expected_answer": expected_answer,
            "chat_history": [build_msg("ai", question)],
            "asked_questions": [question],
            "question_count": question_count + 1,
            "total_questions_asked": question_count + 1,
            "hint_count": 0,
            "hint_counter": 0,
            "request_hint": False,
            "force_move_next": False,
            "forced_penalty": 0,
            "status": "awaiting_answer",
            "progress_message": f"Question {question_count + 1} generated",
        }
    except Exception as e:
        log_progress("question_generator_node", f"Question generation failed: {e}")
        raise InterviewError(f"Question generator failed: {e}") from e


async def human_input_node(state: InterviewSessionState) -> dict[str, Any]:
    """Capture candidate answer through interrupt."""
    log_progress("human_input_node", "Waiting for candidate answer")

    history = state.get("chat_history", [])
    answer = interrupt({"prompt": "Your answer:"})

    return {
        "chat_history": [build_msg("human", str(answer))],
        "answers": [str(answer)],
        "status": "answer_received",
        "progress_message": "Candidate answer captured",
    }


async def analyzer_node(state: InterviewSessionState) -> dict[str, Any]:
    """Analyze candidate's latest answer."""
    log_progress("analyzer_node", "Analyzing candidate answer")

    question = (state.get("asked_questions") or [""])[-1]
    answer = (state.get("answers") or [""])[-1]
    answer_text = str(answer).strip()
    request_hint = "hint" in answer_text.lower()

    parser = JsonOutputParser(pydantic_object=AnalysisResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_ANALYZER + "\n{format_instructions}"),
            ("human", "Question: {q}\nAnswer: {a}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {"q": question, "a": answer},
            get_analysis_service(),
        )

        current_hint_count = int(state.get("hint_count", state.get("hint_counter", 0)) or 0)

        relevance_score = int(out.get("relevance_score", 0) or 0)

        return {
            "analysis": [out],
            "current_relevance_score": relevance_score,
            "hint_count": current_hint_count,
            "hint_counter": current_hint_count,
            "request_hint": request_hint,
            "force_move_next": False,
            "forced_penalty": 0,
            "status": "answer_analyzed",
            "progress_message": "Answer analyzed",
        }
    except Exception as e:
        log_progress("analyzer_node", f"Analysis failed: {e}")
        raise InterviewError(f"Analyzer failed: {e}") from e


async def hint_node(state: InterviewSessionState) -> dict[str, Any]:
    """Provide progressive hint to candidate."""
    log_progress("hint_node", "Generating hint for candidate")

    current_question = state.get("current_question") or (state.get("asked_questions") or [""])[-1]
    expected_answer = str(state.get("expected_answer", "") or "")
    hint_counter = int(state.get("hint_count", state.get("hint_counter", 0)) or 0)
    if hint_counter >= MAX_HINT_COUNT:
        return {
            "chat_history": [
                build_msg(
                    "ai_feedback",
                    "Maximum hints reached for this question. Moving on to the next question.",
                )
            ],
            "request_hint": False,
            "force_move_next": True,
            "forced_penalty": 0,
            "status": "hint_limit_reached",
            "progress_message": "Max hints reached; advancing to evaluator",
        }

    answer = (state.get("answers") or [""])[-1]
    project_summaries = state.get("project_summaries", {})

    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_HINT),
            (
                "human",
                "Question: {q}\nExpected answer: {expected_answer}\nCandidate answer: {a}\n"
                "Project summaries: {project_summaries}\nHint count so far: {hc}\n"
                "Return JSON with key 'hint'.",
            ),
        ]
    )

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "q": current_question,
                "a": answer,
                "expected_answer": expected_answer,
                "hc": hint_counter,
                "project_summaries": json.dumps(project_summaries, ensure_ascii=False),
            },
            get_hint_service(),
        )
        hint_text = str(out.get("hint") or out.get("hint_text") or "").strip()
        if not hint_text:
            hint_text = _build_fallback_hint(current_question, expected_answer, hint_counter)

        log_progress("hint_node", f"Hint {hint_counter + 1} provided")
        return {
            "chat_history": [build_msg("ai_hint", f"Hint: {hint_text}")],
            "hint_count": hint_counter + 1,
            "hint_counter": hint_counter + 1,
            "request_hint": False,
            "force_move_next": False,
            "forced_penalty": 0,
            "status": "hint_provided",
            "progress_message": f"Hint {hint_counter + 1} provided",
        }
    except Exception as e:
        if _is_rate_limit_error(e):
            log_progress("hint_node", f"Hint generation rate-limited: {e}")
            try:
                await asyncio.sleep(_HINT_RATE_LIMIT_RETRY_DELAY_SECONDS)
                out = await invoke_llm_chain(
                    prompt,
                    parser,
                    {
                        "q": current_question,
                        "a": answer,
                        "expected_answer": expected_answer,
                        "hc": hint_counter,
                        "project_summaries": json.dumps(project_summaries, ensure_ascii=False),
                    },
                    get_hint_service(),
                )
                hint_text = str(out.get("hint") or out.get("hint_text") or "").strip()
                if not hint_text:
                    hint_text = _build_fallback_hint(current_question, expected_answer, hint_counter)

                log_progress("hint_node", f"Hint {hint_counter + 1} provided after retry")
                return {
                    "chat_history": [build_msg("ai_hint", f"Hint: {hint_text}")],
                    "hint_count": hint_counter + 1,
                    "hint_counter": hint_counter + 1,
                    "request_hint": False,
                    "force_move_next": False,
                    "forced_penalty": 0,
                    "status": "hint_provided",
                    "progress_message": f"Hint {hint_counter + 1} provided",
                }
            except Exception as retry_error:
                log_progress("hint_node", f"Hint retry failed, using fallback: {retry_error}")

        hint_text = _build_fallback_hint(current_question, expected_answer, hint_counter)
        log_progress("hint_node", f"Hint fallback used: {e}")
        return {
            "chat_history": [build_msg("ai_hint", f"Hint: {hint_text}")],
            "hint_count": hint_counter + 1,
            "hint_counter": hint_counter + 1,
            "request_hint": False,
            "force_move_next": False,
            "forced_penalty": 0,
            "status": "hint_fallback",
            "progress_message": f"Hint {hint_counter + 1} provided",
        }


async def evaluator_node(state: InterviewSessionState) -> dict[str, Any]:
    """Evaluate candidate answer."""
    log_progress("evaluator_node", "Evaluating candidate answer")

    question = (state.get("asked_questions") or [""])[-1]
    analysis = (state.get("analysis") or [{}])[-1]

    if state.get("force_move_next", False):
        skipped_feedback = "Maximum hints reached for this question, so it was skipped."
        status_events = ["evaluated"]
        progress_events = ["Question skipped after max hints"]

        if state.get("total_questions_asked", state.get("question_count", 0)) >= MAX_QUESTIONS:
            status_events.append("interview_completed")
            progress_events.append("Interview completed")

        return {
            "evaluation": [
                {
                    "acknowledgement": "Skipped after max hints",
                    "score": 0.0,
                    "feedback": skipped_feedback,
                    "ideal_response_summary": "",
                }
            ],
            "interview_score": 0.0,
            "question_results": [
                {
                    "question": question,
                    "analysis": analysis,
                    "raw_score": 0.0,
                    "normalized_score": 0.0,
                    "final_score": 0.0,
                    "feedback": skipped_feedback,
                    "ideal_response_summary": "",
                    "hints_used": state.get("hint_count", state.get("hint_counter", 0)),
                }
            ],
            "status_events": status_events,
            "progress_events": progress_events,
            "chat_history": [build_msg("ai_feedback", skipped_feedback)],
            "force_move_next": False,
            "forced_penalty": 0,
        }

    parser = JsonOutputParser(pydantic_object=EvaluationResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_EVALUATOR + "\n{format_instructions}"),
            ("human", "Analysis JSON: {analysis}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {"analysis": json.dumps(analysis, ensure_ascii=False)},
            get_evaluation_service(),
        )

        evals = state.get("evaluation", [])
        score = float(out.get("score", 0))
        avg_score = (sum(float(e.get("score", 0)) for e in evals) + score) / (len(evals) + 1)
        normalized_score = normalize_interview_score(score)
        normalized_avg_score = normalize_interview_score(avg_score)

        status_events = ["evaluated"]
        progress_events = ["Evaluation completed"]

        if state.get("total_questions_asked", state.get("question_count", 0)) >= MAX_QUESTIONS:
            status_events.append("interview_completed")
            progress_events.append("Interview completed")

        feedback_text = f"Score: {normalized_avg_score:.2f}/100. {out.get('feedback', '').strip()}".strip()

        return {
            "evaluation": [out],
            "interview_score": normalized_avg_score,
            "question_results": [
                {
                    "question": question,
                    "analysis": analysis,
                    "raw_score": score,
                    "normalized_score": normalized_score,
                    "final_score": normalized_avg_score,
                    "feedback": out.get("feedback", ""),
                    "ideal_response_summary": out.get("ideal_response_summary", ""),
                    "hints_used": state.get("hint_count", state.get("hint_counter", 0)),
                }
            ],
            "status_events": status_events,
            "progress_events": progress_events,
            "chat_history": [build_msg("ai_feedback", feedback_text)],
            "force_move_next": False,
            "forced_penalty": 0,
        }
    except Exception as e:
        log_progress("evaluator_node", f"Evaluation failed: {e}")
        raise InterviewError(f"Evaluator failed: {e}") from e


async def generate_final_report_node(state: InterviewSessionState) -> dict[str, Any]:
    """Generate final interview report."""
    log_progress("generate_final_report_node", "Generating final interview report")

    parser = JsonOutputParser(pydantic_object=FinalReportResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_FINAL_REPORT + "\n{format_instructions}"),
            ("human", "Questions: {q}\nAnswers: {a}\nAnalysis: {an}\nEvaluation: {ev}\nFinal Score: {fs}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "q": json.dumps(state.get("asked_questions", []), ensure_ascii=False),
                "a": json.dumps(state.get("answers", []), ensure_ascii=False),
                "an": json.dumps(state.get("analysis", []), ensure_ascii=False),
                "ev": json.dumps(state.get("evaluation", []), ensure_ascii=False),
                "fs": state.get("interview_score", 0),
            },
            get_report_service(),
        )

        normalized_average_score = normalize_interview_score(out.get("average_score", state.get("interview_score", 0)))

        final_report = dict(out)
        final_report["average_score"] = normalized_average_score

        return {
            "final_report": final_report,
            "final_summary": f"{out.get('debrief', '')}\nRecommendation: {out.get('recommendation', '')}\nAverage score: {normalized_average_score}",
            "is_complete": True,
            "chat_history": state.get("chat_history", []) + [build_msg("report", out.get("debrief", ""))],
            "interview_end_time": dt.datetime.now(dt.UTC),
            "status": "report_generated",
            "progress_message": "Final interview report generated",
            "phase": "phase_2",
            "phase_label": "Interview Assessment",
        }
    except Exception as e:
        log_progress("generate_final_report_node", f"Report generation failed: {e}")
        raise InterviewError(f"Final report generation failed: {e}") from e