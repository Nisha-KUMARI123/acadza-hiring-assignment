"""
recommender.py
Takes a student analysis + question bank + dost config
and returns a step-by-step personalized study plan.

Logic:
  - Worst chapters (< 30%)  → concept  → practiceAssignment
  - Medium weak (30-55%)    → practiceAssignment → clickingPower
  - Needs practice (55-70%) → pickingPower → speedRace
  - Strengths (>= 70%)      → speedRace (reinforce & boost speed)
  - If slow on tests        → add clickingPower / speedRace step
  - If aborts a lot         → shorter tasks first (formula, clickingPower)
"""

from data_loader import normalize_qid
import re


def strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '').strip()


def filter_questions(
    questions_db: dict,
    chapter: str = None,
    subject: str = None,
    difficulty_max: int = 5,
    difficulty_min: int = 1,
    q_type: str = None,
    count: int = 5,
    exclude_ids: set = None,
) -> list:
    """
    Return up to `count` question IDs matching the filters.
    Tries to match chapter in topic or subtopic fields (case-insensitive).
    """
    exclude_ids = exclude_ids or set()
    matched = []

    chapter_lower  = chapter.lower().replace(" ", "_") if chapter else None
    chapter_words  = chapter.lower().split() if chapter else []
    subject_lower  = subject.lower() if subject else None

    for qid, q in questions_db.items():
        if qid in exclude_ids:
            continue

        # Subject filter
        if subject_lower:
            q_subject = (q.get("subject") or "").lower()
            if subject_lower not in q_subject:
                continue

        # Chapter filter (loose match — topic or subtopic contains the chapter word)
        if chapter_lower:
            topic    = (q.get("topic") or "").lower()
            subtopic = (q.get("subtopic") or "").lower()
            combined = topic + " " + subtopic
            # At least one word from the chapter name must appear
            if not any(w in combined for w in chapter_words if len(w) > 3):
                continue

        # Difficulty filter
        diff = q.get("difficulty")
        if diff is None:
            continue
        if not (difficulty_min <= diff <= difficulty_max):
            continue

        # Question type filter
        if q_type and q.get("questionType") != q_type:
            continue

        matched.append(qid)
        if len(matched) >= count:
            break

    return matched


def pick_dost(avg_pct: float, slow: bool = False, aborts: bool = False) -> list:
    """
    Given a chapter's average %, return an ordered list of DOST types to recommend.
    Returns a list so we can create multiple steps per weak chapter.
    """
    if aborts:
        # Prefer shorter, less intimidating tasks first
        if avg_pct < 30:
            return ["formula", "concept", "clickingPower"]
        elif avg_pct < 55:
            return ["formula", "clickingPower", "practiceAssignment"]
        else:
            return ["clickingPower", "pickingPower"]

    if avg_pct < 30:
        return ["concept", "practiceAssignment"]
    elif avg_pct < 55:
        return ["practiceAssignment", "clickingPower"]
    elif avg_pct < 70:
        return ["pickingPower", "speedRace"]
    else:
        return ["speedRace"]


def student_message(dost_type: str, chapter: str, avg_pct: float) -> str:
    """Generate a friendly, motivating message to the student."""
    messages = {
        "concept": f"Let's revisit the theory behind {chapter} — a strong foundation will unlock everything else.",
        "formula": f"Quick formula revision for {chapter}! Even 10 minutes here will pay off in the test.",
        "practiceAssignment": f"Time to practice {chapter} with targeted questions — no timer, just focus.",
        "practiceTest":       f"Take a full mock test on {chapter} — exam simulation mode!",
        "revision":           f"A structured revision plan for {chapter} — let's lock in those concepts.",
        "clickingPower":      f"Speed drill on {chapter}! 10 rapid questions — train your instincts.",
        "pickingPower":       f"MCQ elimination practice for {chapter} — learn to rule out wrong options fast.",
        "speedRace":          f"You're doing well in {chapter} — race against the bot and push your speed!",
    }
    return messages.get(dost_type, f"Study session for {chapter}.")


def recommend_student(
    student_id: str,
    analysis: dict,
    questions_db: dict,
    dost_config: dict,
) -> dict:
    """
    Build a personalized step-by-step DOST study plan.

    Returns:
      { student_id, plan: [ {step, dost_type, chapter, parameters,
                              question_ids, reason, message}, ... ] }
    """
    steps = []
    step_num = 1
    used_qids = set()

    weaknesses    = analysis.get("weaknesses", [])
    needs_practice = analysis.get("needs_practice", [])
    strengths     = analysis.get("strengths", [])
    ch_avg        = analysis.get("chapter_averages", {})
    subj_avg      = analysis.get("subject_averages", {})
    slow_sessions = analysis.get("slow_sessions", 0)
    total         = analysis.get("total_attempts", 1)
    aborted       = analysis.get("aborted_attempts", 0)

    is_slow   = slow_sessions > total * 0.4
    is_aborter = aborted > 0

    # ── STEP BUILDER HELPER ──
    def add_step(dost_type, chapter, reason, q_count=5, diff_max=5, diff_min=1, subject=None):
        nonlocal step_num

        # Get questions relevant to this chapter
        avg = ch_avg.get(chapter, 50)
        # Easier questions for very weak chapters
        if avg < 30:
            diff_max = 2
        elif avg < 50:
            diff_max = 3

        qids = filter_questions(
            questions_db,
            chapter=chapter,
            subject=subject,
            difficulty_min=diff_min,
            difficulty_max=diff_max,
            count=q_count,
            exclude_ids=used_qids,
        )
        used_qids.update(qids)

        params = dost_config.get(dost_type, {})

        steps.append({
            "step":         step_num,
            "dost_type":    dost_type,
            "chapter":      chapter,
            "subject":      subject or "General",
            "parameters":   params,
            "question_ids": qids,
            "reason":       reason,
            "message":      student_message(dost_type, chapter, ch_avg.get(chapter, 50)),
        })
        step_num += 1

    # ── PHASE 1: Address Weaknesses (worst first) ──
    for chapter in weaknesses[:3]:   # Focus on top 3 weakest
        avg = ch_avg.get(chapter, 0)
        dost_sequence = pick_dost(avg, slow=is_slow, aborts=is_aborter)

        for dost in dost_sequence[:2]:  # Max 2 steps per chapter
            reason = (
                f"Average score in {chapter} is only {avg}% — "
                f"{'needs foundational work' if avg < 30 else 'targeted practice needed'}."
            )
            add_step(dost, chapter, reason)

    # ── PHASE 2: Needs Practice chapters ──
    for chapter in needs_practice[:2]:
        avg = ch_avg.get(chapter, 60)
        dost_sequence = pick_dost(avg, slow=is_slow, aborts=is_aborter)
        reason = f"{chapter} is at {avg}% — just needs more targeted drilling to push above 70%."
        add_step(dost_sequence[0], chapter, reason)

    # ── PHASE 3: Speed boost if student is slow ──
    if is_slow and len(steps) < 8:
        # Pick a chapter they know reasonably well for speed drill
        target = (needs_practice + strengths or list(ch_avg.keys()))
        if target:
            ch = target[0]
            reason = f"You tend to run over time in timed tests — speed drill on {ch} will help."
            add_step("clickingPower", ch, reason, q_count=10)

    # ── PHASE 4: Reinforce Strengths (confidence + speed) ──
    for chapter in strengths[:1]:
        avg = ch_avg.get(chapter, 75)
        reason = f"{chapter} is a strong area ({avg}%) — keep the edge sharp with a speed race!"
        add_step("speedRace", chapter, reason, diff_max=5, diff_min=3)

    # ── PHASE 5: Full Mock if overall score is decent ──
    overall = analysis.get("overall_score", 0)
    if overall >= 50 and step_num <= 8:
        # Pick the subject they're best at for a mock
        if subj_avg:
            best_subj = max(subj_avg, key=subj_avg.get)
            reason = (
                f"Overall score is {overall}% — time to simulate exam conditions "
                f"and test {best_subj} under pressure."
            )
            steps.append({
                "step":         step_num,
                "dost_type":    "practiceTest",
                "chapter":      "Mixed",
                "subject":      best_subj,
                "parameters":   dost_config.get("practiceTest", {}),
                "question_ids": filter_questions(
                    questions_db, subject=best_subj,
                    count=25, exclude_ids=used_qids
                ),
                "reason":       reason,
                "message":      f"Full mock test in {best_subj} — exam simulation mode. Give it your best!",
            })
            step_num += 1

    return {
        "student_id":  student_id,
        "total_steps": len(steps),
        "summary":     f"Focus areas: {', '.join(weaknesses[:3]) or 'General improvement'}",
        "plan":        steps,
    }