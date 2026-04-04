# Acadza AI Intern Assignment — Student Recommender System

## Overview

This project is a FastAPI-based recommender system built for Acadza's JEE/NEET EdTech platform. It reads student performance data across multiple test and assignment sessions, analyzes their patterns, and generates a personalized step-by-step study plan using Acadza's 8 DOST (Dynamic Optimized Study Task) types.

---

## Setup & Running

```bash
# 1. Clone and enter the repo
git clone https://github.com/YOUR_USERNAME/acadza-hiring-assignment
cd acadza-hiring-assignment

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload

# 4. Open browser
# API docs → http://127.0.0.1:8000/docs
# Health   → http://127.0.0.1:8000/
```

To generate sample outputs for all 10 students:
```bash
# (Server must be running first)
python generate_outputs.py
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze/{student_id}` | Full performance analysis |
| POST | `/recommend/{student_id}` | Step-by-step DOST study plan |
| GET  | `/question/{question_id}` | Clean question lookup |
| GET  | `/leaderboard` | Ranked leaderboard of all students |

---

## My Approach to the Build Task

### Analyzing Student Data

My first instinct was to look at the data before writing a single line of code. I opened `student_performance.json` and noticed a few things immediately: the marks field was a mess (more on that below), some students had a mix of timed tests and untimed assignments, and the chapters list could have multiple entries per attempt.

I grouped all attempts by `student_id` and then computed per-chapter averages by collecting marks across all sessions where that chapter appeared. This gives a cleaner picture than just looking at the last attempt — a student who scored 30%, 40%, 50% in Thermodynamics is clearly improving, which a single snapshot would miss.

I also computed behavioral signals — completion rate, skip rate, and whether the student frequently ran over the allotted time. These matter for recommendations: recommending a 60-minute mock test to someone who aborts 3 out of 5 sessions is counterproductive.

### Choosing Which DOSTs to Recommend

I built a simple priority ladder:

- **Below 30%** in a chapter → start with `concept` (theory first), then `practiceAssignment` (no timer, just focus)
- **30–55%** → `practiceAssignment` then `clickingPower` (speed drill to build fluency)
- **55–70%** → `pickingPower` (MCQ elimination practice) then `speedRace`
- **Above 70%** → `speedRace` (keep the edge sharp)

For students who abort a lot, I switch to shorter, less intimidating tasks: `formula` revision and `clickingPower` before longer assignments. The idea is to build a habit of completing tasks before increasing difficulty.

Each step also includes real question IDs from `question_bank.json`, filtered by chapter (loose keyword match against topic/subtopic) and calibrated difficulty (easier questions for weaker chapters).

---

## Handling the Messy Marks Field

This was the trickiest part. The `marks` field appears in at least 5 formats:

1. Plain integer: `72`
2. Plain string number: `"28"`
3. Fraction: `"68/100"`
4. Positive/negative: `"+52 -8"` (marks gained minus marks lost)
5. Fraction with percentage: `"34/75 (45.3%)"`

My approach was to write a `normalize_marks()` function using regex, checking each format in order of specificity. The `+52 -8` format was the tricky one — I treated it as `52/(52+8)` which gives a percentage of correct marks out of total attempted marks (both correct and incorrect attempts). I return `None` for truly unparseable values so downstream code can handle them gracefully rather than silently treating them as zero.

Edge case I noticed: raw numbers like `28` could mean 28/100 or 28/75 depending on the exam pattern. Without knowing the denominator, I treat these as a direct percentage score capped at 100. This is an assumption — given more context (exam_pattern or total_marks fields), I'd refine this.

---

## Debug Process

I opened `debug/recommender_buggy.py` and ran it. It didn't crash, but the recommendations felt wrong — stronger students were getting beginner-level tasks and vice versa.

I added `print()` statements at every decision point to trace what score was being computed for each chapter and what DOST was being selected. The comparison logic for classifying students as "weak" or "strong" had the operator direction flipped — students above a threshold were being flagged as weak and vice versa. Once I spotted that, the fix was a one-line change. I've corrected the file and explained the exact line in a comment.

I tried using Claude to spot the bug first — it found a different potential issue (a sorting direction) that turned out to be a red herring. The real bug required manual tracing.

---

## What I'd Improve With More Time

1. **Better chapter matching**: My current question filter uses keyword matching against topic/subtopic. A proper mapping from chapter names to canonical topic keys would be more reliable.
2. **Multi-session trend-aware recommendations**: Instead of averaging all sessions equally, use recent sessions with higher weight — a student who improved in the last 2 sessions shouldn't be penalized by old low scores.
3. **Collaborative filtering**: Find students with similar performance profiles and recommend what helped similar students improve.
4. **LLM-generated messages**: The student-facing messages are template-based now. Generating them with an LLM would make them more personal and context-aware.
5. **Difficulty progression within a plan**: Steps should escalate difficulty automatically as the plan progresses, not stay at a fixed level.

---

## File Structure

```
├── main.py                  # FastAPI app + all 4 endpoints
├── data_loader.py           # JSON loading + marks normalization
├── analyzer.py              # analyze_student() logic
├── recommender.py           # recommend_student() logic
├── generate_outputs.py      # Batch output generator
├── requirements.txt
├── README.md
├── data/
│   ├── student_performance.json
│   ├── question_bank.json
│   └── dost_config.json
├── debug/
│   └── recommender_buggy.py   # Fixed version with explanation
└── sample_outputs/
    └── student_XXX_analyze.json / student_XXX_recommend.json  (×10 each)
```