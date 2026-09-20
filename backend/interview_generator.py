"""
Interview Generator Module
Creates personalized interview questions based on the candidate's resume.
Uses an LLM API when available, with a comprehensive fallback engine.
"""

import os
import re
import json
import random
from typing import Dict, Any, List, Optional

try:
    import requests
except ImportError:
    requests = None


# ── Question Categories ────────────────────────────────────────────────

QUESTION_CATEGORIES = [
    "resume_introduction",
    "experience_deep_dive",
    "project_deep_dive",
    "technical_skills",
    "problem_solving",
    "achievements",
    "leadership_teamwork",
    "challenges_failures",
    "career_decisions",
    "clarification",
]

# ── Rubric Templates ───────────────────────────────────────────────────

def get_rubric_for_category(category: str) -> Dict[str, str]:
    """Get evaluation rubric based on question category."""
    base_rubric = {
        "relevance": "Does the answer directly address the question asked?",
        "accuracy": "Is the answer consistent with the information in the resume?",
        "specificity": "Does the answer include specific details, names, numbers, or concrete examples?",
        "examples": "Does the answer reference real projects, tasks, or situations?",
        "structure": "Does the answer follow a clear structure (situation, task, action, result)?",
        "depth": "Does the answer demonstrate genuine technical or professional understanding?",
        "clarity": "Is the answer well-articulated and easy to follow?",
        "completeness": "Does the answer cover all aspects of the question?",
    }

    category_specific = {
        "resume_introduction": {
            "relevance": "Does the introduction cover the key points from the resume?",
            "depth": "Does the introduction demonstrate career progression and purpose?",
        },
        "project_deep_dive": {
            "specificity": "Does the answer describe the project architecture, tools, and personal contributions?",
            "examples": "Does the answer include measurable outcomes or results from the project?",
            "depth": "Does the answer demonstrate understanding of technical trade-offs?",
        },
        "technical_skills": {
            "depth": "Does the answer demonstrate hands-on experience with the mentioned technologies?",
            "specificity": "Does the answer describe how the skills were applied in practice?",
        },
        "achievements": {
            "examples": "Does the answer include quantifiable results and measurable impact?",
            "structure": "Does the answer clearly explain context, action, and outcome?",
        },
        "challenges_failures": {
            "structure": "Does the answer describe the challenge, approach, and resolution?",
            "depth": "Does the answer show reflection and learning from the experience?",
        },
        "leadership_teamwork": {
            "specificity": "Does the answer describe specific team situations and personal role?",
            "examples": "Does the answer include concrete outcomes of the teamwork or leadership?",
        },
    }

    if category in category_specific:
        base_rubric.update(category_specific[category])

    return base_rubric


# ── LLM Provider Configuration ──────────────────────────────────────

def get_llm_config() -> Optional[Dict[str, str]]:
    """Resolve LLM provider settings from environment variables.

    Supports Groq (OpenAI-compatible) first, then OpenAI.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return {
            "api_url": "https://api.groq.com/openai/v1/chat/completions",
            "api_key": groq_key,
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        }

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return {
            "api_url": "https://api.openai.com/v1/chat/completions",
            "api_key": openai_key,
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }

    return None


# ── LLM-based Question Generation ─────────────────────────────────────

def generate_questions_with_llm(profile: Dict[str, Any], resume_text: str) -> Optional[List[Dict[str, Any]]]:
    """Generate questions using an LLM API if available."""
    config = get_llm_config()
    if not config or not requests:
        return None

    profile_summary = json.dumps(profile, indent=2, default=str)[:3000]
    resume_excerpt = resume_text[:2000]

    prompt = f"""You are a friendly, experienced human interviewer conducting a 1-on-1 career coaching session. Generate exactly 10 personalized interview questions based on the candidate's resume.

IMPORTANT: Write questions as a real human interviewer would — conversational, warm, direct. NOT formal or robotic. Use natural phrasing like "So, I see you worked at..." or "Tell me about..." or "I'm curious about...".

CANDIDATE PROFILE:
{profile_summary}

RESUME EXCERPT:
{resume_excerpt}

Generate questions across these categories:
1. Resume introduction (1 question) — Start naturally: "So, tell me a bit about yourself and your journey."
2. Most important experience (1 question)
3. Project deep dive (2 questions)
4. Technical/functional skills (1 question)
5. Problem-solving (1 question)
6. Achievements and measurable results (1 question)
7. Leadership or teamwork (1 question)
8. Challenges and failures (1 question)
9. Career decisions (1 question)

For each question, provide a JSON object with:
- "question_text": The question to ask
- "category": One of: resume_introduction, experience_deep_dive, project_deep_dive, technical_skills, problem_solving, achievements, leadership_teamwork, challenges_failures, career_decisions, clarification

Return ONLY a JSON array of objects. No other text."""

    try:
        resp = requests.post(
            config["api_url"],
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "You are a professional interview question generator. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Extract JSON from possible markdown code block
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                questions = json.loads(json_match.group(0))
                return questions
    except Exception:
        pass

    return None


# ── Fallback Rule-Based Question Generation ────────────────────────────

def generate_fallback_questions(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate questions based on resume content using rules."""
    questions = []
    name = profile.get("name", "the candidate")
    summary = profile.get("summary", "")
    job_titles = profile.get("job_titles", [])
    companies = profile.get("companies", [])
    skills = profile.get("skills", [])
    tools = profile.get("tools_and_tech", [])
    projects = profile.get("projects", [])
    achievements = profile.get("achievements", [])
    education = profile.get("education", [])
    measurable = profile.get("measurable_results", [])
    missing = profile.get("missing_or_unclear", [])

    primary_title = job_titles[0] if job_titles else "your professional role"
    primary_company = companies[0] if companies else None

    # Category 1: Resume Introduction — conversational opening
    intro_q = f"So, tell me a bit about yourself. How did you get into {primary_title}, and what's the journey been like so far?"
    if summary:
        intro_q = f"I see you describe yourself as experienced in {summary[:80]}... I'd love to hear more about that — what drew you to this field and where has your career taken you?"
    questions.append({
        "question_text": intro_q,
        "category": "resume_introduction",
    })

    # Category 2: Most Important Experience — conversational
    if primary_company:
        exp_q = f"I see you spent some time at {primary_company}. What would you say was your biggest contribution there — the thing you're most proud of?"
    elif job_titles:
        exp_q = f"Thinking about your time as a {primary_title}, what's the one thing you've done that you feel made the biggest difference?"
    else:
        exp_q = "If you had to pick one thing you've accomplished in your career that you're most proud of, what would it be?"
    questions.append({
        "question_text": exp_q,
        "category": "experience_deep_dive",
    })

    # Category 3: Project Deep Dives — conversational
    if projects:
        proj = projects[0]
        proj_name = proj.get("name", "your notable project")
        questions.append({
            "question_text": f"I noticed you worked on {proj_name}. Walk me through that — what was your role, what made it tricky, and how did it turn out?",
            "category": "project_deep_dive",
        })
        if len(projects) > 1:
            proj2 = projects[1]
            questions.append({
                "question_text": f"You also worked on {proj2.get('name', 'another project')}. How did that one differ from your other work, and what did you take away from it?",
                "category": "project_deep_dive",
            })
        else:
            questions.append({
                "question_text": "Tell me about a time when things got a bit unclear on a project — maybe requirements shifted or you had to figure things out as you went. How did you handle that?",
                "category": "project_deep_dive",
            })
    else:
        questions.append({
            "question_text": "What's a project you've worked on that you're genuinely proud of? Tell me what the problem was, what you did about it, and what the result was."
            ,"category": "project_deep_dive",
        })
        questions.append({
            "question_text": "Have you ever been in a situation where a project didn't go quite as planned? What happened, and how did you deal with it?",
            "category": "project_deep_dive",
        })

    # Category 4: Technical Skills — conversational
    if skills or tools:
        all_tech = (skills + tools)[:5]
        tech_str = ", ".join(all_tech)
        questions.append({
            "question_text": f"I see you've worked with {tech_str}. Can you tell me about a specific time you used one of these to solve a real problem? I'm curious about the nuts and bolts of how you work."
            ,"category": "technical_skills",
        })
    else:
        questions.append({
            "question_text": "What would you say are your strongest technical skills? And more importantly, can you give me an example of how you've used them to tackle something challenging?"
            ,"category": "technical_skills",
        })

    # Category 5: Problem Solving — conversational
    questions.append({
        "question_text": "Can you think of a time when you ran into a really tricky problem at work? How did you go about figuring it out?",
        "category": "problem_solving",
    })

    # Category 6: Achievements — conversational
    if measurable:
        achievement = measurable[0]
        questions.append({
            "question_text": f"You mentioned something that caught my eye: {achievement}. That's impressive. Can you break down how you made that happen and what the numbers actually looked like?"
            ,"category": "achievements",
        })
    elif achievements:
        questions.append({
            "question_text": f"I noticed you highlighted: {achievements[0]}. Tell me more about that — what was your role in making it happen, and how did you measure the impact?"
            ,"category": "achievements",
        })
    else:
        questions.append({
            "question_text": "What's an accomplishment at work that you feel doesn't get enough attention? What made it significant?",
            "category": "achievements",
        })

    # Category 7: Leadership/Teamwork — conversational
    questions.append({
        "question_text": "Tell me about a time you were working with a team and things got a bit tense — maybe there were different opinions on how to approach something. How did you navigate that?"
        ,"category": "leadership_teamwork",
    })

    # Category 8: Challenges/Failures — conversational, safe
    questions.append({
        "question_text": "We've all had things go sideways at work. Can you tell me about a time that happened to you — what went wrong and what did you take away from it?"
        ,"category": "challenges_failures",
    })

    # Category 9: Career Decisions — conversational
    if job_titles and len(job_titles) > 1:
        questions.append({
            "question_text": f"I see you went from {job_titles[-1]} to {job_titles[0]}. What prompted that change? What were you looking for in your next move?"
            ,"category": "career_decisions",
        })
    else:
        questions.append({
            "question_text": "When you think about your career, what's driving your decisions? Where do you see things going in the next few years?"
            ,"category": "career_decisions",
        })

    # Category 10: Clarification — conversational, not accusatory
    if missing:
        missing_str = " and ".join(missing[:2])
        questions.append({
            "question_text": f"I had a couple of questions about your resume — I noticed {missing_str} weren't included. Would you mind filling those in for me?"
            ,"category": "clarification",
        })

    return questions


# ── Follow-up Question Generation ──────────────────────────────────────

def generate_followup_with_llm(
    question: str,
    answer: str,
    profile: Dict[str, Any],
    category: str,
) -> Optional[str]:
    """Generate a follow-up question using LLM."""
    config = get_llm_config()
    if not config or not requests:
        return None

    prompt = f"""You are a professional interview coach conducting a personalized interview.

CANDIDATE PROFILE SUMMARY: {json.dumps(profile, default=str)[:1500]}

CURRENT QUESTION: "{question}"
QUESTION CATEGORY: {category}
CANDIDATE'S ANSWER: "{answer}"

Generate exactly ONE follow-up question based on the candidate's answer. The follow-up should:
1. Probe deeper into a specific claim or detail the candidate mentioned
2. Ask for clarification if the answer was vague
3. Request a specific example if the answer was too general
4. Challenge a claim that seems inconsistent with the resume

Keep it professional, concise (1-2 sentences), and natural.
Return ONLY the follow-up question text. No quotes, no explanation."""

    try:
        resp = requests.post(
            config["api_url"],
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config["model"],
                "messages": [
                    {"role": "system", "content": "You are a professional interviewer. Return only the follow-up question text."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean up any surrounding quotes
            content = content.strip('"').strip("'")
            if content and len(content) > 10:
                return content
    except Exception:
        pass

    return None


def generate_followup_fallback(
    question: str,
    answer: str,
    profile: Dict[str, Any],
    category: str,
) -> str:
    """Generate a follow-up question using rules when LLM is unavailable."""
    words = answer.split()
    word_count = len(words)
    answer_lower = answer.lower()

    # Detect answer characteristics
    is_vague = word_count < 15
    is_long = word_count > 200
    has_metrics = bool(re.search(r'\d+[%$x]|\d+\.\d+|percent|million|billion|thousand', answer_lower))
    has_examples = bool(re.search(r'for example|such as|specifically|instance|one time|when i|we had', answer_lower))
    mentions_challenge = bool(re.search(r'challenge|difficult|problem|issue|failure|struggle|obstacle', answer_lower))

    # Follow-up templates based on answer quality
    if is_vague:
        return "Thank you for that overview. Could you go deeper and provide a specific example with concrete details about what you personally did and what the outcome was?"

    if not has_metrics and not has_examples:
        return "That's a good starting point. Can you add a specific example with measurable results to strengthen this point?"

    if has_examples and not has_metrics:
        return "Great example. Can you quantify the impact of that work — for instance, how much time or money it saved, or what improvement metrics you observed?"

    if mentions_challenge:
        return "You mentioned facing challenges. Can you walk me through the specific steps you took to overcome them and what you learned from the experience?"

    if is_long:
        return "That was quite detailed — thank you. To focus on the key takeaway: what would you say was the single most important decision you made in that situation?"

    # Category-specific follow-ups
    category_followups = {
        "resume_introduction": "What specific area of your work excites you most right now, and how does it connect to the experience shown in your resume?",
        "project_deep_dive": "Can you describe the technical architecture you chose for that project and why you made those specific design decisions?",
        "technical_skills": "Can you describe a specific scenario where you applied that skill to solve a complex problem under pressure?",
        "problem_solving": "What was the root cause of that problem, and how did you confirm your diagnosis before implementing the solution?",
        "achievements": "How did you measure that success, and what was your specific contribution versus the team's collective effort?",
        "leadership_teamwork": "How did you handle any disagreements within the team, and what specific outcome did your leadership produce?",
        "challenges_failures": "What would you do differently if you faced the same situation today, and what specific safeguards did you put in place afterward?",
        "career_decisions": "What was the deciding factor in that career move, and how did it shape your professional goals going forward?",
        "experience_deep_dive": "Can you walk me through a specific day or week in that role to give me a sense of your actual responsibilities and impact?",
        "clarification": "Could you provide more details about this, including the timeline, your role, and the specific outcome?",
    }

    if category in category_followups:
        return category_followups[category]

    return "Thank you for that answer. Could you elaborate with a specific example that demonstrates the impact of your work?"


def should_ask_followup(answer: str, question_category: str) -> bool:
    """Determine if a follow-up question should be asked based on answer quality."""
    words = answer.split()
    word_count = len(words)

    # Always ask follow-up for very short answers
    if word_count < 15:
        return True

    # Ask for vague answers without examples
    has_examples = bool(re.search(r'for example|such as|specifically|when i|we had|one time|built|created|implemented|designed', answer.lower()))
    if word_count < 40 and not has_examples:
        return True

    # Ask about 30% of the time for medium answers to keep interview natural
    if word_count < 80:
        return random.random() < 0.4

    # Occasionally probe very long answers
    if word_count > 200:
        return random.random() < 0.3

    return random.random() < 0.2


# ── Main Entry Points ──────────────────────────────────────────────────

def generate_interview_questions(profile: Dict[str, Any], resume_text: str = "") -> List[Dict[str, Any]]:
    """
    Generate a complete set of interview questions from the resume.
    Uses LLM if available, falls back to rule-based generation.
    """
    # Try LLM first
    llm_questions = generate_questions_with_llm(profile, resume_text)
    if llm_questions and len(llm_questions) >= 5:
        # Ensure each question has required fields
        result = []
        for i, q in enumerate(llm_questions):
            result.append({
                "question_text": q.get("question_text", q.get("question", "")),
                "category": q.get("category", QUESTION_CATEGORIES[i % len(QUESTION_CATEGORIES)]),
            })
        return result[:12]

    # Fallback to rule-based
    return generate_fallback_questions(profile)


def generate_followup(
    question: str,
    answer: str,
    profile: Dict[str, Any],
    category: str = "general",
) -> str:
    """Generate a follow-up question for the given answer."""
    llm_followup = generate_followup_with_llm(question, answer, profile, category)
    if llm_followup:
        return llm_followup
    return generate_followup_fallback(question, answer, profile, category)
