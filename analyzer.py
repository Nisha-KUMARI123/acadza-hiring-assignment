"""
analyzer.py
Takes a student's list of attempts and returns a detailed analysis:
  - chapter-wise breakdown
  - subject-wise breakdown
  - strengths and weaknesses
  - behavioral patterns (slow, aborting, skipping)
  - trend over time
"""

from collections import defaultdict
from data_loader import normalize_marks
import re


def strip_html(text: str) -> str:
    """Remove HTML tags from question text."""
    return re.sub(r'<[^>]+>', '', text or '').strip()


def analyze_student(student_id: str, attempts: list) -> dict:
    """
    Full analysis of a student's performance.

    Returns a dict with:
      student_id, total_attempts, completion_rate,
      chapter_averages, subject_averages,
      strengths, weaknesses,
      patterns, trend, overall_score
    """
    if not attempts:
        return {
            "student_id": student_id,
            "error": "No attempts found for this student"
        }

    # ── Aggregators ──
    chapter_marks   = defaultdict(list)   # chapter → [pct, ...]
    subject_marks   = defaultdict(list)   # subject  → [pct, ...]
    chapter_attempts = defaultdict(int)   # chapter → count
    subject_attempts = defaultdict(int)

    total          = 0
    completed      = 0
    aborted        = 0
    total_skipped  = 0
    total_questions = 0
    slow_count     = 0    # sessions where student ran overtime
    marks_over_time = []  # for trend

    for attempt in attempts:
        total += 1
        pct = attempt.get("marks_pct")

        if attempt.get("completed"):
            completed += 1
        else:
            aborted += 1

        chapters = attempt.get("chapters", [])
        subject  = attempt.get("subject", "Unknown")

        # Skip detection
        skipped  = attempt.get("skipped", 0) or 0
        n_q      = attempt.get("total_questions", 0) or 0
        total_skipped  += skipped
        total_questions += n_q

        # Slow detection: time_taken > duration (only for timed tests)
        dur   = attempt.get("duration_minutes")
        taken = attempt.get("time_taken_minutes")
        if dur and taken and taken > dur * 1.05:   # 5% grace
            slow_count += 1

        if pct is not None:
            for ch in chapters:
                chapter_marks[ch].append(pct)
                chapter_attempts[ch] += 1
            subject_marks[subject].append(pct)
            subject_attempts[subject] += 1
            marks_over_time.append(pct)

    # ── Averages ──
    chapter_averages = {
        ch: round(sum(v) / len(v), 1)
        for ch, v in chapter_marks.items()
    }
    subject_averages = {
        s: round(sum(v) / len(v), 1)
        for s, v in subject_marks.items()
    }

    # ── Strengths & Weaknesses ──
    strengths  = sorted(
        [ch for ch, avg in chapter_averages.items() if avg >= 70],
        key=lambda c: -chapter_averages[c]
    )
    weaknesses = sorted(
        [ch for ch, avg in chapter_averages.items() if avg < 55],
        key=lambda c: chapter_averages[c]   # worst first
    )
    # Chapters in the middle (55-70%) — needs practice
    needs_practice = [
        ch for ch, avg in chapter_averages.items()
        if 55 <= avg < 70
    ]

    # ── Completion Rate ──
    completion_rate = round((completed / total) * 100, 1) if total else 0

    # ── Skip Rate ──
    skip_rate = round((total_skipped / total_questions) * 100, 1) if total_questions else 0

    # ── Overall Score (weighted avg of all marks_pct) ──
    overall_score = round(sum(marks_over_time) / len(marks_over_time), 1) if marks_over_time else 0

    # ── Trend ──
    trend = "insufficient data"
    if len(marks_over_time) >= 3:
        first_half = marks_over_time[:len(marks_over_time)//2]
        second_half = marks_over_time[len(marks_over_time)//2:]
        avg_first  = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        diff = avg_second - avg_first
        if diff > 5:
            trend = "improving"
        elif diff < -5:
            trend = "declining"
        else:
            trend = "stable"

    # ── Behavioral Patterns ──
    patterns = []
    if aborted > 0:
        patterns.append(f"Aborts tests — {aborted} out of {total} sessions not completed")
    if skip_rate > 20:
        patterns.append(f"High skip rate — {skip_rate}% of questions skipped on average")
    if slow_count > total * 0.4:
        patterns.append("Tends to run overtime on timed tests — needs speed practice")
    if completion_rate == 100:
        patterns.append("Excellent discipline — completes every session")
    if not patterns:
        patterns.append("No major behavioral concerns detected")

    return {
        "student_id":         student_id,
        "total_attempts":     total,
        "completed_attempts": completed,
        "aborted_attempts":   aborted,
        "completion_rate":    completion_rate,
        "overall_score":      overall_score,
        "trend":              trend,
        "skip_rate_pct":      skip_rate,
        "slow_sessions":      slow_count,
        "chapter_averages":   chapter_averages,
        "subject_averages":   subject_averages,
        "strengths":          strengths,
        "weaknesses":         weaknesses,
        "needs_practice":     needs_practice,
        "patterns":           patterns,
        "marks_timeline":     marks_over_time,
    }