"""
main.py
FastAPI application for Acadza Student Recommender System.

Endpoints:
  POST /analyze/{student_id}     → performance analysis
  POST /recommend/{student_id}   → step-by-step DOST plan
  GET  /question/{question_id}   → question lookup (normalized)
  GET  /leaderboard              → ranked list of all students
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import re

from data_loader import get_all_data, normalize_qid
from analyzer import analyze_student, strip_html
from recommender import recommend_student

app = FastAPI(
    title="Acadza Student Recommender API",
    description=(
        "Analyzes JEE/NEET student performance data and "
        "recommends personalized DOST study plans."
    ),
    version="1.0.0",
)

# ── Load data once at startup ──
@app.on_event("startup")
def startup():
    get_all_data()   # populates cache
    print("[main] All data loaded and cached.")


# ─────────────────────────────────────────────
# POST /analyze/{student_id}
# ─────────────────────────────────────────────

@app.post(
    "/analyze/{student_id}",
    summary="Analyze a student's performance across all sessions",
    tags=["Analysis"],
)
def analyze(student_id: str):
    """
    Returns chapter-wise breakdown, strengths, weaknesses,
    behavioral patterns, and overall trend for the given student.
    """
    data     = get_all_data()
    students = data["students"]

    if student_id not in students:
        raise HTTPException(
            status_code=404,
            detail=f"Student '{student_id}' not found. "
                   f"Available: {list(students.keys())}",
        )

    attempts = students[student_id]
    result   = analyze_student(student_id, attempts)
    return JSONResponse(content=result)


# ─────────────────────────────────────────────
# POST /recommend/{student_id}
# ─────────────────────────────────────────────

@app.post(
    "/recommend/{student_id}",
    summary="Get a personalized step-by-step DOST study plan",
    tags=["Recommendation"],
)
def recommend(student_id: str):
    """
    Analyzes the student first, then builds a step-by-step
    plan using DOST types from dost_config.json with real
    question IDs from question_bank.json.
    """
    data      = get_all_data()
    students  = data["students"]
    questions = data["questions"]
    dost_cfg  = data["dost_config"]

    if student_id not in students:
        raise HTTPException(
            status_code=404,
            detail=f"Student '{student_id}' not found.",
        )

    attempts = students[student_id]
    analysis = analyze_student(student_id, attempts)
    plan     = recommend_student(student_id, analysis, questions, dost_cfg)
    return JSONResponse(content=plan)


# ─────────────────────────────────────────────
# GET /question/{question_id}
# ─────────────────────────────────────────────

@app.get(
    "/question/{question_id}",
    summary="Look up a question by ID",
    tags=["Questions"],
)
def get_question(question_id: str):
    """
    Returns clean question data.
    Handles both $oid format and plain string IDs.
    Strips HTML from question text.
    """
    data      = get_all_data()
    questions = data["questions"]

    # Normalize the incoming ID
    norm_id = normalize_qid(question_id)

    q = questions.get(norm_id) or questions.get(question_id)

    if not q:
        raise HTTPException(
            status_code=404,
            detail=f"Question '{question_id}' not found.",
        )

    qtype   = q.get("questionType", "scq")
    content = q.get(qtype) or q.get("scq") or q.get("mcq") or q.get("integerQuestion") or {}

    # Strip HTML from question preview
    raw_text    = content.get("question", "")
    plain_text  = strip_html(raw_text)[:300]   # preview up to 300 chars

    return JSONResponse(content={
        "question_id":   norm_id,
        "type":          qtype,
        "subject":       q.get("subject"),
        "topic":         q.get("topic"),
        "subtopic":      q.get("subtopic"),
        "difficulty":    q.get("difficulty"),
        "question_preview": plain_text,
        "answer":        content.get("answer"),
        "solution_available": bool(content.get("solution")),
    })


# ─────────────────────────────────────────────
# GET /leaderboard
# ─────────────────────────────────────────────

def compute_leaderboard_score(analysis: dict) -> float:
    """
    Scoring formula:
      - 60% weight on overall average marks
      - 25% weight on completion rate
      - 15% bonus for consistency (trend)

    Max possible score ≈ 100
    """
    avg_marks       = analysis.get("overall_score", 0)
    completion_rate = analysis.get("completion_rate", 0)
    trend           = analysis.get("trend", "stable")

    trend_bonus = {"improving": 10, "stable": 5, "declining": 0,
                   "insufficient data": 3}.get(trend, 3)

    score = (avg_marks * 0.60) + (completion_rate * 0.25) + trend_bonus
    return round(score, 2)


@app.get(
    "/leaderboard",
    summary="Rank all students by performance score",
    tags=["Leaderboard"],
)
def leaderboard():
    """
    Ranks all 10 students using a weighted scoring formula:
      60% overall marks + 25% completion rate + 15% trend bonus.

    Returns rank, score, top strength, top weakness, and recommended focus area.
    """
    data     = get_all_data()
    students = data["students"]

    ranked = []
    for sid, attempts in students.items():
        analysis = analyze_student(sid, attempts)
        score    = compute_leaderboard_score(analysis)

        # Top strength / weakness
        strengths  = analysis.get("strengths", [])
        weaknesses = analysis.get("weaknesses", [])
        ch_avg     = analysis.get("chapter_averages", {})

        top_strength = strengths[0] if strengths else "—"
        top_weakness = weaknesses[0] if weaknesses else "—"

        # Focus area: worst weakness if any, else needs_practice, else strengths
        focus_area = (
            weaknesses[0] if weaknesses
            else (analysis.get("needs_practice") or ["General improvement"])[0]
        )

        ranked.append({
            "student_id":   sid,
            "score":        score,
            "overall_pct":  analysis.get("overall_score", 0),
            "completion":   analysis.get("completion_rate", 0),
            "trend":        analysis.get("trend", "—"),
            "top_strength": top_strength,
            "top_weakness": top_weakness,
            "focus_area":   focus_area,
        })

    # Sort by score descending
    ranked.sort(key=lambda x: -x["score"])

    # Add rank
    for i, entry in enumerate(ranked, start=1):
        entry["rank"] = i

    return JSONResponse(content={"leaderboard": ranked})


# ─────────────────────────────────────────────
# Root health check
# ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "running",
        "message": "Acadza Recommender API is live.",
        "docs": "/docs",
        "endpoints": [
            "POST /analyze/{student_id}",
            "POST /recommend/{student_id}",
            "GET  /question/{question_id}",
            "GET  /leaderboard",
        ],
    }