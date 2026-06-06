"""LangGraph nodes for interview workflow."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from typing import Any
import uuid

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import interrupt

from app.core.retrieval import retrieve_relevant_cv_chunks
from .constants import MAX_QUESTIONS, MAX_RESUME_LENGTH, MAX_JD_LENGTH, MAX_HINT_COUNT
from .exceptions import InterviewError, LLMError
from .helpers import log_progress, build_msg
from .helpers import normalize_interview_score
from .prompts import (
    SYSTEM_GREETING,
    SYSTEM_STRATEGY,
    SYSTEM_QUESTION_GENERATOR,
    SYSTEM_ANALYZER,
    SYSTEM_HINT,
    SYSTEM_EVALUATOR,
    SYSTEM_FINAL_REPORT,
    SYSTEM_CHAT_SUMMARY,
)
from .schemas import (
    GreetingResult,
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
    get_summary_chat_service,
)
from .state import InterviewSessionState

from app.core.retrieval import retrieve_relevant_cv_chunks


_HINT_RATE_LIMIT_RETRY_DELAY_SECONDS = 1.5


def _get_language_directive(preferred_language: str) -> str:
    """Returns language instruction for user-facing prompts."""
    if preferred_language == 'ar':
        return "IMPORTANT: You MUST respond in Arabic. Write all questions, feedback, hints, and responses in Arabic only. Do NOT write in English."
    return "IMPORTANT: You MUST respond in English. Write all questions, feedback, hints, and responses in English only."


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate limit" in message or "rate_limit_exceeded" in message


async def greeting_node(state: InterviewSessionState) -> dict[str, Any]:
    """Generate greeting message for the candidate."""
    log_progress("greeting_node", "Generating interview greeting")

    interview_data = state.get("interview_data", {})
    job_title = state.get("job_title", "the position")
    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    candidate_name = "there"
    personal_info = interview_data.get("personal_info", {})
    if personal_info and personal_info.get("name"):
        candidate_name = personal_info.get("name", "there")
    else:
        cv_text = state.get("resume_text", "")
        if cv_text and len(cv_text) > 0:
            lines = cv_text.split('\n')
            for line in lines[:10]:
                if line.strip() and len(line.split()) <= 3:
                    candidate_name = line.strip().title()
                    break

    parser = JsonOutputParser(pydantic_object=GreetingResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_GREETING + "\n{language_instruction}\n{format_instructions}"),
            ("human", "Candidate Name: {candidate_name}\nJob Title: {job_title}"),
        ]
    ).partial(
        format_instructions=parser.get_format_instructions(),
        language_instruction=lang_directive,
    )

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "candidate_name": candidate_name,
                "job_title": job_title,
            },
            get_strategy_service(),
        )

        greeting_text = out.get("greeting", "").strip()
        if not greeting_text:
            greeting_text = f"Hello {candidate_name}! I'm excited to conduct your interview for the {job_title} position. Are you ready to begin?"

        log_progress("greeting_node", "Greeting generated successfully")

        return {
            "pending_greeting": greeting_text,
            "status": "greeting_ready",
            "progress_message": "Greeting prepared",
        }
    except Exception as e:
        log_progress("greeting_node", f"Greeting generation failed: {e}")
        fallback_greeting = f"Hello! Welcome to your technical interview for {job_title}. Are you ready to begin?"
        return {
            "pending_greeting": fallback_greeting,
            "status": "greeting_ready",
            "progress_message": "Greeting prepared (fallback)",
        }


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

    print(f"Preferred language for strategy node: {state.get("preferred_language", "i don't found")}")
    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    parser = JsonOutputParser(pydantic_object=NextQuestion)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_STRATEGY + "\n{language_instruction}\n{format_instructions}"),
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
    ).partial(format_instructions=parser.get_format_instructions(), language_instruction=lang_directive)

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
    log_progress("question_generator_node", "Generating next interview question")

    pending_greeting = state.get("pending_greeting", "")
    asked = state.get("asked_questions", [])
    answers = state.get("answers", [])
    analysis = state.get("analysis", [])
    strategy = state.get("strategy", {})
    question_count = int(state.get("total_questions_asked", state.get("question_count", 0)) or 0)
    feedback_on_previous = state.get("feedback_on_previous_answer", "")

    if question_count >= MAX_QUESTIONS:
        return {
            "chat_history": [build_msg("ai", "Thanks. We have completed all interview questions.")],
            "status": "interview_completed",
            "progress_message": "Interview completed",
        }

    missing_skills = list(state.get("missing_skills", []))
    matched_skills = list(state.get("matched_skills", []))
    
    all_skills = missing_skills + matched_skills
    
    target_skill = None
    if question_count < len(all_skills):
        target_skill = all_skills[question_count]
    elif all_skills:
        target_skill = all_skills[0]
    else:
        target_skill = "General"

    rag_context = ""
    question_instruction_type = "GENERAL"
    
    if target_skill:
        try:
            interview_data = state.get("interview_data", {})
            resume_id_str = interview_data.get("resume_id")
            
            if resume_id_str:
                search_query = f"How {target_skill} was implemented in project"
                chunks = await retrieve_relevant_cv_chunks(
                    resume_id=uuid.UUID(resume_id_str),
                    query_text=search_query,
                    top_k=1
                )
                
                if chunks:
                    rag_context = chunks[0]
                else:
                    rag_context = ""
                    log_progress("question_generator_node", "No strong RAG context found, switching to general logic via prompt")
        except Exception as e:
            log_progress("question_generator_node", f"RAG search failed: {e}")
            rag_context = ""


    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    parser = JsonOutputParser(pydantic_object=NextQuestion)
    has_greeting = bool(pending_greeting and question_count == 0)
    
    bridge_context = ""
    if feedback_on_previous and question_count > 0:
        bridge_context = f"\n=== PREVIOUS ANSWER CONTEXT ===\n{feedback_on_previous}\n"

    prompt_content = (
            f"{bridge_context}"
            "Target Skill: {target_skill}\n\n"
            "=== RETRIEVED CONTEXT (From Resume/Projects) ===\n"
            "{rag_context}\n\n"
            "=== INSTRUCTIONS ===\n"
            "You must ask a question about '{target_skill}'.\n"
            "DECISION LOGIC:\n"
            "- If the RETRIEVED CONTEXT above contains detailed implementation details (algorithms, architecture, specific code patterns), "
            "ask a SPECIFIC question based on that context (e.g., 'In your project regarding X, how did you handle Y?').\n"
            "- If the RETRIEVED CONTEXT is empty, generic, or only lists tool names, "
            "ask a GENERAL CONCEPTUAL question (e.g., 'What are the trade-offs of using X?').\n\n"
            "=== OTHER CONTEXT ===\n"
            "Job Title: {job_title}\n"
            "Job Requirements: {job_requirements}\n"
            "Previous Answers: {answers}\n"
            f"PENDING GREETING (combine with first question if exists): {pending_greeting}\n"
            "REMEMBER: Be conversational."
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_QUESTION_GENERATOR + "\n{language_instruction}\n{format_instructions}"),
            ("human", prompt_content),
        ]
    ).partial(format_instructions=parser.get_format_instructions(), language_instruction=lang_directive)

    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            {
                "target_skill": target_skill,
                "rag_context": rag_context,
                "job_title": state.get("job_title", ""),
                "job_requirements": json.dumps(list(state.get("job_requirements", [])), ensure_ascii=False),
                "answers": json.dumps(asked[-1:], ensure_ascii=False),
                "pending_greeting": pending_greeting if has_greeting else "",
            },
            get_question_service(),
        )

        question = out["question"].strip()
        expected_answer = out.get("expected_answer", "").strip()

        log_progress("question_generator_node", f"Question {question_count + 1} generated")
    
    except Exception as e:
        log_progress("question_generator_node", f"Question generation failed: {e}")
        question = "Could you tell me more about your experience with the technologies we discussed?"
        expected_answer = ""

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
        "pending_greeting": "",
        "is_first_turn": False,
        "forced_penalty": 0,
        "status": "awaiting_answer",
        "progress_message": f"Question {question_count + 1} generated",
    }


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

    interview_data = state.get("interview_data", {})
    resume_id = interview_data.get("resume_id")
    
    cv_context = ""
    
    if resume_id:
        try:
            search_query = f"Question: {question}\nAnswer: {answer}"
            
            relevant_chunks = await retrieve_relevant_cv_chunks(
                resume_id=uuid.UUID(resume_id),
                query_text=search_query,
                top_k=3
            )
            
            if relevant_chunks:
                cv_context = "\n\n--- FROM CANDIDATE'S RESUME (Reference) ---\n" + "\n\n".join(relevant_chunks)
                
        except Exception as e:
            log_progress("analyzer_node", f"RAG retrieval failed: {e}")

    parser = JsonOutputParser(pydantic_object=AnalysisResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_ANALYZER + "\n{format_instructions}"),
            ("human", "Question: {q}\nAnswer: {a}")
        ]
    ).partial(cv_context=cv_context, format_instructions=parser.get_format_instructions())

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
    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_HINT + "\n{language_instruction}"),
            (
                "human",
                "Question: {q}\nExpected answer: {expected_answer}\nCandidate answer: {a}\n"
                "Project summaries: {project_summaries}\nHint count so far: {hc}\n"
                "Return JSON with key 'hint'.",
            ),
        ]
    ).partial(language_instruction=lang_directive)

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
    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_EVALUATOR + "\n{language_instruction}\n{format_instructions}"),
            ("human", "Analysis JSON: {analysis}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions(), language_instruction=lang_directive)

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
            "feedback_on_previous_answer": f"{out.get('acknowledgement', '')} {out.get('feedback', '')}".strip(),
        }
    except Exception as e:
        log_progress("evaluator_node", f"Evaluation failed: {e}")
        raise InterviewError(f"Evaluator failed: {e}") from e


async def generate_final_report_node(state: InterviewSessionState) -> dict[str, Any]:
    """Generate final interview report."""
    log_progress("generate_final_report_node", "Generating final interview report")

    parser = JsonOutputParser(pydantic_object=FinalReportResult)
    
    full_transcript = state.get("full_transcript", [])
    
    if full_transcript:
        human_message_text = (
            "Full Interview Transcript:\n{transcript}\n\n"
            "Detailed Analysis & Evaluation Data:\n"
            "Analysis: {an}\n"
            "Evaluations: {ev}\n"
            "Current Calculated Score: {fs}"
        )
        payload = {
            "transcript": "\n".join(full_transcript),
            "an": json.dumps(state.get("analysis", []), ensure_ascii=False),
            "ev": json.dumps(state.get("evaluation", []), ensure_ascii=False),
            "fs": state.get("interview_score", 0),
        }
    else:
        human_message_text = (
            "Questions: {q}\n"
            "Answers: {a}\n"
            "Analysis: {an}\n"
            "Evaluation: {ev}\n"
            "Final Score: {fs}"
        )
        
        payload = {
            "q": json.dumps(state.get("asked_questions", []), ensure_ascii=False),
            "a": json.dumps(state.get("answers", []), ensure_ascii=False),
            "an": json.dumps(state.get("analysis", []), ensure_ascii=False),
            "ev": json.dumps(state.get("evaluation", []), ensure_ascii=False),
            "fs": state.get("interview_score", 0),
        }
    
    preferred_language = state.get("preferred_language", "en")
    lang_directive = _get_language_directive(preferred_language)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_FINAL_REPORT + "\n{language_instruction}\n{format_instructions}"),
            ("human", human_message_text),
        ]
    ).partial(format_instructions=parser.get_format_instructions(), language_instruction=lang_directive)
    
    try:
        out = await invoke_llm_chain(
            prompt,
            parser,
            payload,
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
    

async def summarize_history_node(state: InterviewSessionState) -> dict[str, Any]:
    """Summarizes the conversation history to save context window and cost."""
    log_progress("summarize_history_node", "Compressing interview history")

    current_history = state.get("chat_history", [])
    

    if len(current_history) < 6: 
        return {}

    history_text_for_archive = [f"{msg.get('role')}: {msg.get('content')}" for msg in current_history]
    
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_CHAT_SUMMARY),
        ("human", "Conversation History:\n{history}")
    ])
    
    summary = ""
    try:
        chain = prompt | get_summary_chat_service().client
        summary_output = await chain.ainvoke({"history": "\n".join(history_text_for_archive)})
        summary = str(summary_output).strip()
    except Exception as e:
        log_progress("summarize_history_node", f"Summarization failed, keeping history: {e}")
        return {} 

    last_turn = current_history[-2:] if len(current_history) >= 2 else current_history
    
    system_context_msg = {
        "role": "system", 
        "content": f"INTERVIEW SUMMARY SO FAR:\n{summary}\n\nContinue the interview based on this summary and the latest answer."
    }
    
    log_progress("summarize_history_node", "History compressed successfully")
    
    return {
        "chat_history": [system_context_msg] + last_turn,
        "full_transcript": history_text_for_archive
    }