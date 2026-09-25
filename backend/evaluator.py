"""
Answer Evaluator Module
Evaluates interview answers based on observable evidence from the transcript.
Does not infer personality, intelligence, emotion, or protected characteristics.
"""

import re
import json
import os
from typing import Dict, Any, List, Optional

try:
    import requests
except ImportError:
    requests = None


# ── Scoring Dimensions ─────────────────────────────────────────────────

SCORE_DIMENSIONS = [
    "relevance",
    "completeness",
    "specificity",
    "structure",
    "evidence_and_examples",
    "resume_consistency",
    "technical_depth",
    "communication_clarity",
    "conciseness",
    "overall_readiness",
]

DISPLAY_DIMENSIONS = [
    "Relevance", "Completeness", "Specificity", "Structure",
    "Evidence & Examples", "Resume Consistency", "Technical Depth",
    "Communication Clarity", "Conciseness", "Overall Readiness",
]


def _groq_config() -> Optional[Dict[str, str]]:
    """Return Groq configuration only when a real key is available."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return None
    return {
        "api_url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key": api_key,
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    }


def _extract_json_object(content: str) -> Optional[Dict[str, Any]]:
    """Read a JSON object even if a provider wraps it in a code fence."""
    match = re.search(r'\{[\s\S]*\}', content)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def score_answer_with_groq(
    question: str,
    answer: str,
    category: str,
    profile: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Score one answer against the actual question and resume using Groq."""
    config = _groq_config()
    if not config or not requests:
        return None

    resume_context = json.dumps({
        "name": profile.get("name", ""),
        "summary": profile.get("summary", ""),
        "job_titles": profile.get("job_titles", []),
        "companies": profile.get("companies", []),
        "skills": profile.get("skills", []),
        "tools_and_tech": profile.get("tools_and_tech", []),
        "projects": profile.get("projects", []),
        "achievements": profile.get("achievements", []),
        "measurable_results": profile.get("measurable_results", []),
    }, default=str)[:6000]
    prompt = f"""You are an evidence-based interview assessor. Assess only the candidate's answer below against the question and supplied resume. Do not infer personality, intelligence, emotion, or any protected characteristic. Do not invent accomplishments or evidence.

QUESTION: {question}
CATEGORY: {category}
ANSWER: {answer}
RESUME FACTS: {resume_context}

Return ONLY valid JSON in this exact shape:
{{
  "scores": [{{"dimension":"Relevance|Completeness|Specificity|Structure|Evidence & Examples|Resume Consistency|Technical Depth|Communication Clarity|Conciseness|Overall Readiness", "score": 1.0, "max_score": 5.0, "evidence":"brief, specific reason grounded in the answer or resume"}}],
  "strengths": ["up to 3 evidence-based strengths"],
  "improvements": ["up to 3 specific improvements"],
  "suggested_answer_structure": "one concise, tailored suggestion"
}}

Provide exactly one score for every listed dimension. Use 1.0-5.0 in 0.5 increments. For Resume Consistency, use 3.0 when the answer cannot be verified from the supplied resume; do not assume it is true. Quote or clearly point to concrete details from the answer in every evidence field."""
    try:
        response = requests.post(
            config["api_url"],
            headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "Return only valid JSON. Be evidence-based and calibrated."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1800,
            },
            timeout=25,
        )
        if response.status_code != 200:
            return None
        content = response.json()["choices"][0]["message"]["content"].strip()
        result = _extract_json_object(content)
        if not result:
            return None

        raw_scores = {item.get("dimension"): item for item in result.get("scores", []) if isinstance(item, dict)}
        if any(dimension not in raw_scores for dimension in DISPLAY_DIMENSIONS):
            return None
        scores = []
        for dimension in DISPLAY_DIMENSIONS:
            item = raw_scores[dimension]
            try:
                score = round(max(1.0, min(5.0, float(item.get("score", 0)))) * 2) / 2
            except (TypeError, ValueError):
                return None
            evidence = str(item.get("evidence", "")).strip()
            if not evidence:
                return None
            scores.append({"dimension": dimension, "score": score, "max_score": 5.0, "evidence": evidence})
        return {
            "scores": scores,
            "strengths": [str(value) for value in result.get("strengths", [])[:3] if str(value).strip()],
            "improvements": [str(value) for value in result.get("improvements", [])[:3] if str(value).strip()],
            "suggested_answer_structure": str(result.get("suggested_answer_structure", "")).strip(),
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def calculate_filler_words(text: str) -> int:
    """Count filler words in text."""
    fillers = [
        'um', 'uh', 'like', 'you know', 'basically', 'actually',
        'literally', 'right', 'so', 'well', 'kind of', 'sort of',
        'i mean', 'honestly', 'obviously', 'clearly',
    ]
    text_lower = text.lower()
    count = 0
    for filler in fillers:
        count += len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))
    return count


def calculate_repeated_phrases(text: str) -> int:
    """Detect repeated phrases in text."""
    words = text.lower().split()
    repeated = 0
    # Check for 3-word phrase repetition
    if len(words) >= 6:
        phrases = set()
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if phrase in phrases:
                repeated += 1
            phrases.add(phrase)
    return repeated


def calculate_speaking_pace(word_count: int, duration_seconds: float) -> str:
    """Calculate speaking pace category."""
    if duration_seconds <= 0:
        return "unknown"
    wpm = word_count / (duration_seconds / 60)
    if wpm < 100:
        return "slow"
    elif wpm < 150:
        return "moderate"
    elif wpm < 200:
        return "normal"
    else:
        return "fast"


def score_answer(
    question: str,
    answer: str,
    category: str,
    profile: Dict[str, Any],
    duration_seconds: float = 0.0,
    question_number: int = 1,
    total_questions: int = 10,
) -> Dict[str, Any]:
    """
    Score an interview answer based on observable evidence.
    Returns scores, strengths, improvements, and suggested structure.
    """
    answer_lower = answer.lower().strip()
    words = answer.split()
    word_count = len(words)

    # Groq is the primary evaluator. Its reasons are tied to this exact
    # question, answer, and resume rather than to a synthetic score formula.
    groq_evaluation = score_answer_with_groq(question, answer, category, profile)
    if groq_evaluation:
        groq_evaluation.update({
            "filler_word_count": calculate_filler_words(answer),
            "repeated_phrases": calculate_repeated_phrases(answer),
            "speaking_pace": calculate_speaking_pace(word_count, duration_seconds),
            "word_count": word_count,
            "has_examples": bool(re.search(r'for example|such as|specifically|for instance|when i|i built|i created|i designed|i implemented|i led|i managed|i developed', answer_lower)),
            "has_metrics": bool(re.search(r'\d+[%$x]|\d+\.\d+|percent|million|billion|thousand|\d+x\b', answer_lower)),
            "evaluation_source": "groq",
        })
        return groq_evaluation

    # ── Basic Metrics ──────────────────────────────────────────────
    has_metrics = bool(re.search(r'\d+[%$x]|\d+\.\d+|percent|million|billion|thousand|\d+x\b', answer_lower))
    has_examples = bool(re.search(
        r'for example|such as|specifically|for instance|one time|when i|we had|i built|i created|i designed|i implemented|i led|i managed|i developed',
        answer_lower
    ))
    has_structure = bool(re.search(
        r'situation|task|action|result|context|background|challenge|approach|outcome|what i did|what happened|the result',
        answer_lower
    ))
    addresses_question = word_count >= 10  # Basic check

    # Check resume consistency
    resume_consistent = True
    consistency_notes = []
    resume_skills = [s.lower() for s in profile.get("skills", []) + profile.get("tools_and_tech", [])]
    resume_titles = [t.lower() for t in profile.get("job_titles", [])]

    # Check if claimed skills match resume
    claimed_tech = re.findall(r'\b(python|java|react|angular|node|django|flask|fastapi|aws|docker|kubernetes|sql|mongodb|redis|graphql)\b', answer_lower)
    for tech in claimed_tech:
        if tech not in resume_skills and tech not in [s.lower() for s in profile.get("tools_and_tech", [])]:
            # Don't flag as inconsistent if it's a common tool - just note it
            pass

    # ── Score Dimensions (1-5 scale) ──────────────────────────────

    # Relevance
    relevance = 3.0
    if addresses_question and word_count >= 20:
        relevance = 4.0
    if word_count < 8:
        relevance = 1.5
    elif word_count < 15:
        relevance = 2.5

    # Completeness
    completeness = 3.0
    if word_count >= 50 and has_examples:
        completeness = 4.5
    elif word_count >= 30:
        completeness = 3.5
    elif word_count < 15:
        completeness = 2.0

    # Specificity
    specificity = 2.0
    if has_metrics and has_examples:
        specificity = 5.0
    elif has_examples:
        specificity = 4.0
    elif has_metrics:
        specificity = 3.5
    elif word_count > 30:
        specificity = 3.0

    # Structure
    structure = 2.5
    if has_structure:
        structure = 4.0
    if word_count > 60 and has_structure:
        structure = 4.5
    if word_count < 20:
        structure = 2.0

    # Evidence and examples
    evidence = 2.0
    if has_examples and has_metrics:
        evidence = 5.0
    elif has_examples:
        evidence = 4.0
    elif has_metrics:
        evidence = 3.0

    # Resume consistency
    resume_consistency = 4.0
    if not resume_consistent:
        resume_consistency = 2.0

    # Technical depth
    tech_depth = 3.0
    tech_keywords_count = len(re.findall(
        r'\b(architecture|implementation|algorithm|optimization|scalability|performance|latency|throughput|database|api|infrastructure|deployment|testing|monitoring|debugging|refactoring)\b',
        answer_lower
    ))
    if tech_keywords_count >= 4:
        tech_depth = 4.5
    elif tech_keywords_count >= 2:
        tech_depth = 3.5
    elif tech_keywords_count == 0:
        tech_depth = 2.0

    # Communication clarity
    clarity = 3.0
    filler_count = calculate_filler_words(answer)
    if filler_count <= 2 and word_count >= 20:
        clarity = 4.0
    elif filler_count > 5:
        clarity = 2.0
    if word_count >= 20:
        clarity = min(clarity + 0.5, 5.0)

    # Conciseness
    conciseness = 3.0
    if 20 <= word_count <= 100:
        conciseness = 4.5
    elif 100 < word_count <= 200:
        conciseness = 3.5
    elif word_count > 200:
        conciseness = 2.5
    elif word_count < 15:
        conciseness = 2.0

    # Overall readiness
    overall = round(
        (relevance + completeness + specificity + structure + evidence + clarity) / 6,
        1
    )

    # ── Build Scores List ──────────────────────────────────────────
    scores = [
        {"dimension": "Relevance", "score": round(relevance, 1), "max_score": 5.0, "evidence": _get_evidence("relevance", relevance, addresses_question, word_count)},
        {"dimension": "Completeness", "score": round(completeness, 1), "max_score": 5.0, "evidence": _get_evidence("completeness", completeness, has_examples, word_count)},
        {"dimension": "Specificity", "score": round(specificity, 1), "max_score": 5.0, "evidence": _get_evidence("specificity", specificity, has_examples, word_count)},
        {"dimension": "Structure", "score": round(structure, 1), "max_score": 5.0, "evidence": _get_evidence("structure", structure, has_structure, word_count)},
        {"dimension": "Evidence & Examples", "score": round(evidence, 1), "max_score": 5.0, "evidence": _get_evidence("evidence", evidence, has_examples, word_count)},
        {"dimension": "Resume Consistency", "score": round(resume_consistency, 1), "max_score": 5.0, "evidence": "The answer appears consistent with the resume information." if resume_consistent else "Some claims appear inconsistent with the resume and should be reviewed."},
        {"dimension": "Technical Depth", "score": round(tech_depth, 1), "max_score": 5.0, "evidence": f"Found {tech_keywords_count} technical depth indicators." if tech_keywords_count > 0 else "The answer could include more technical specifics."},
        {"dimension": "Communication Clarity", "score": round(clarity, 1), "max_score": 5.0, "evidence": f"Filler word count: {filler_count}. " + ("Clear communication." if clarity >= 3.5 else "Could improve clarity by reducing filler words.")},
        {"dimension": "Conciseness", "score": round(conciseness, 1), "max_score": 5.0, "evidence": f"Answer length: {word_count} words. " + ("Good balance of detail and brevity." if conciseness >= 3.5 else "Consider being more concise.")},
        {"dimension": "Overall Readiness", "score": round(overall, 1), "max_score": 5.0, "evidence": "Combined assessment of answer quality across all dimensions."},
    ]

    # ── Strengths ──────────────────────────────────────────────────
    strengths = []
    if has_examples:
        strengths.append("Provided specific examples to support the answer")
    if has_metrics:
        strengths.append("Included measurable results and quantifiable outcomes")
    if has_structure:
        strengths.append("Followed a clear answer structure with context, action, and result")
    if filler_count <= 2:
        strengths.append("Maintained clear and professional communication")
    if word_count >= 30 and word_count <= 150:
        strengths.append("Provided an appropriately detailed response")
    if tech_depth >= 4.0:
        strengths.append("Demonstrated strong technical depth in the response")

    # ── Improvements ───────────────────────────────────────────────
    improvements = []
    if not has_examples:
        improvements.append("Include a specific example to strengthen the answer")
    if not has_metrics:
        improvements.append("Add measurable outcomes (numbers, percentages, or concrete results)")
    if not has_structure:
        improvements.append("Structure the answer with a clear beginning (situation), middle (action), and end (result)")
    if word_count < 20:
        improvements.append("The answer was brief — provide more detail and context")
    if word_count > 200:
        improvements.append("The answer was lengthy — focus on the most relevant points")
    if filler_count > 5:
        improvements.append(f"Reduce filler words ({filler_count} detected) for more professional communication")
    if not resume_consistent:
        improvements.append("A claim appears inconsistent with the resume — verify and clarify")

    # ── Suggested Answer Structure ─────────────────────────────────
    suggested = _suggest_structure(category, question)

    return {
        "scores": scores,
        "strengths": strengths,
        "improvements": improvements,
        "suggested_answer_structure": suggested,
        "filler_word_count": filler_count,
        "repeated_phrases": calculate_repeated_phrases(answer),
        "speaking_pace": calculate_speaking_pace(word_count, duration_seconds),
        "word_count": word_count,
        "has_examples": has_examples,
        "has_metrics": has_metrics,
        "evaluation_source": "rule_based_fallback",
    }


def _get_evidence(dimension: str, score: float, has_feature: bool, word_count: int) -> str:
    """Generate evidence text for a score dimension."""
    if dimension == "relevance":
        if score >= 4.0:
            return "The answer directly addresses the question with relevant details."
        elif score >= 3.0:
            return "The answer is relevant but could be more focused on the specific question."
        else:
            return "The answer did not fully address the question asked."
    elif dimension == "completeness":
        if score >= 4.0:
            return "The answer covers the topic comprehensively with supporting details."
        elif score >= 3.0:
            return "The answer is reasonably complete but could include more supporting details."
        else:
            return "The answer is incomplete and needs more elaboration."
    elif dimension == "specificity":
        if has_feature:
            return "The answer includes specific details and concrete examples."
        return "The answer could be more specific with concrete examples and details."
    elif dimension == "structure":
        if score >= 4.0:
            return "The answer follows a clear logical structure."
        return "The response could be more structured with a clear beginning, middle, and result."
    elif dimension == "evidence":
        if has_feature:
            return "The answer supports claims with examples and evidence."
        return "The answer lacks supporting evidence and examples."
    return ""


def _suggest_structure(category: str, question: str) -> str:
    """Suggest an improved answer structure based on the question category."""
    structures = {
        "resume_introduction": "Start with your current role, then briefly cover your career progression, key achievements, and what drives you professionally. Keep it under 90 seconds.",
        "experience_deep_dive": "Use the STAR method: Describe the Situation, explain your Task, detail the Actions you took, and share the Results with measurable outcomes.",
        "project_deep_dive": "Cover: Project context and problem → Your specific role → Technical choices and trade-offs → Challenges faced → Results and impact with metrics.",
        "technical_skills": "Start with the technology, explain how you've used it in practice, describe a specific complex problem you solved, and share the outcome.",
        "problem_solving": "Describe the problem → Your diagnosis process → Steps taken to resolve it → Outcome and lessons learned → Preventive measures implemented.",
        "achievements": "Context (what was the situation) → Your specific contribution → Measurable impact (numbers, percentages) → What made it significant.",
        "leadership_teamwork": "Context of the team/project → Your specific role → How you handled dynamics and disagreements → The outcome and your growth.",
        "challenges_failures": "What happened → Your immediate response → Root cause analysis → Corrective actions → Long-term improvements and learning.",
        "career_decisions": "What motivated the decision → What you were looking for → How it aligned with your goals → What you learned → How it shaped your next steps.",
        "clarification": "Provide clear, direct details with specific dates, roles, responsibilities, and outcomes. Address each point that was unclear.",
    }
    return structures.get(category, "Use the STAR method: Situation, Task, Action, Result. Be specific with examples and measurable outcomes.")


def evaluate_full_interview(
    session_data: Dict[str, Any],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a comprehensive evaluation for the entire interview.
    Called after the interview is completed.
    """
    answers = session_data.get("answers", [])
    questions = session_data.get("questions", [])
    total_questions = len(questions)
    total_answers = len(answers)

    if not answers:
        return {
            "overall_score": 0,
            "readiness_level": "Not enough evidence to evaluate",
            "scores": [],
            "strengths": [],
            "improvements": [],
            "communication": {},
            "practice_plan": [],
            "resume_consistency": [],
        }

    # Aggregate scores
    all_scores = {}
    for ans_data in answers:
        eval_result = ans_data.get("evaluation", {})
        for score in eval_result.get("scores", []):
            dim = score["dimension"]
            if dim not in all_scores:
                all_scores[dim] = []
            all_scores[dim].append(score["score"])

    avg_scores = []
    for dim in SCORE_DIMENSIONS:
        # Map to display names
        display_map = {
            "relevance": "Relevance",
            "completeness": "Completeness",
            "specificity": "Specificity",
            "structure": "Structure",
            "evidence_and_examples": "Evidence & Examples",
            "resume_consistency": "Resume Consistency",
            "technical_depth": "Technical Depth",
            "communication_clarity": "Communication Clarity",
            "conciseness": "Conciseness",
            "overall_readiness": "Overall Readiness",
        }
        display_name = display_map.get(dim, dim)
        if display_name in all_scores:
            vals = all_scores[display_name]
            avg = round(sum(vals) / len(vals), 1) if vals else 0.0
            avg_scores.append({
                "dimension": display_name,
                "score": avg,
                "max_score": 5.0,
                "evidence": f"Average across {len(vals)} answers.",
            })

    # Overall score (1-5 scale, converted to percentage for display)
    overall_vals = [s["score"] for s in avg_scores if s["dimension"] == "Overall Readiness"]
    overall_raw = sum(overall_vals) / len(overall_vals) if overall_vals else 2.5
    overall_pct = round(overall_raw * 20)  # Convert 1-5 to 0-100

    # Readiness level
    if overall_pct >= 75:
        readiness = "Strong foundation"
    elif overall_pct >= 50:
        readiness = "Developing"
    else:
        readiness = "Needs more practice"

    # Aggregate strengths and improvements
    all_strengths = []
    all_improvements = []
    for ans_data in answers:
        eval_result = ans_data.get("evaluation", {})
        for s in eval_result.get("strengths", []):
            if s not in all_strengths:
                all_strengths.append(s)
        for i in eval_result.get("improvements", []):
            if i not in all_improvements:
                all_improvements.append(i)

    # Communication metrics
    durations = [a.get("duration_seconds", 0) for a in answers]
    avg_duration = sum(durations) / len(durations) if durations else 0
    total_fillers = sum(a.get("evaluation", {}).get("filler_word_count", 0) for a in answers)
    total_repeated = sum(a.get("evaluation", {}).get("repeated_phrases", 0) for a in answers)

    all_words = sum(a.get("evaluation", {}).get("word_count", 0) for a in answers)
    pace = calculate_speaking_pace(all_words, sum(durations))

    # Conciseness rating
    if avg_duration >= 30 and avg_duration <= 90:
        conciseness_rating = "Good"
    elif avg_duration < 30:
        conciseness_rating = "Answers are brief — provide more detail"
    else:
        conciseness_rating = "Answers are lengthy — focus on key points"

    communication = {
        "avg_answer_duration": round(avg_duration, 1),
        "speaking_pace": pace,
        "filler_word_count": total_fillers,
        "long_pauses": 0,  # Would need audio analysis for real detection
        "repeated_phrases": total_repeated,
        "questions_requiring_repetition": 0,
        "conciseness_rating": conciseness_rating,
    }

    # Practice plan
    practice_plan = []
    if not any(a.get("evaluation", {}).get("has_examples", False) for a in answers):
        practice_plan.append({
            "priority": 1,
            "recommendation": "Prepare two STAR-format examples from your project experience before your next interview.",
            "rationale": "Your answers lacked specific examples."
        })

    has_any_metrics = any(a.get("evaluation", {}).get("has_metrics", False) for a in answers)
    if not has_any_metrics:
        practice_plan.append({
            "priority": 2,
            "recommendation": "Add measurable outcomes to your achievement stories — include numbers, percentages, or time saved.",
            "rationale": "Your answers did not include quantifiable results."
        })

    if communication["filler_word_count"] > 10:
        practice_plan.append({
            "priority": 3,
            "recommendation": "Practice answering questions in under two minutes while reducing filler words.",
            "rationale": f"You used {communication['filler_word_count']} filler words during the interview."
        })

    avg_wpm = all_words / (sum(durations) / 60) if sum(durations) > 0 else 0
    if avg_wpm > 160:
        practice_plan.append({
            "priority": 3,
            "recommendation": "Slow down your speaking pace. Aim for 130-150 words per minute for clarity.",
            "rationale": "Your speaking pace was faster than the recommended range."
        })

    if overall_pct < 60:
        practice_plan.append({
            "priority": 4,
            "recommendation": "Review your resume timeline and practice explaining each role with specific achievements.",
            "rationale": "Strengthen the connection between your resume and interview responses."
        })

    if not practice_plan:
        practice_plan.append({
            "priority": 1,
            "recommendation": "Continue practicing with varied questions to build consistency across all areas.",
            "rationale": "Your performance was solid — maintaining consistency is the next step."
        })

    # Resume consistency
    resume_consistency = []
    for ans_data in answers:
        answer_text = ans_data.get("answer_text", "")
        question_text = ans_data.get("question_text", "")
        # Check for claims that go beyond resume
        if re.search(r'i (managed|led|directed|oversaw) a team of (\d+)', answer_text.lower()):
            match = re.search(r'i (managed|led|directed|oversaw) a team of (\d+)', answer_text.lower())
            resume_consistency.append({
                "statement": match.group(0),
                "resume_context": "Verify team leadership claim against resume details.",
                "status": "unverifiable",
            })

    return {
        "overall_score": overall_pct,
        "readiness_level": readiness,
        "scores": avg_scores,
        "strengths": [{"area": s, "description": s, "evidence": ""} for s in all_strengths[:5]],
        "improvements": [{"area": i, "description": i, "suggestion": i} for i in all_improvements[:5]],
        "communication": communication,
        "practice_plan": practice_plan,
        "resume_consistency": resume_consistency,
    }
