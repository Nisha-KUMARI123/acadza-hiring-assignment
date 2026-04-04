import json
import re
import os
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def normalize_marks(marks):
    if marks is None:
        return None
    if isinstance(marks, (int, float)):
        return min(float(marks), 100.0)
    s = str(marks).strip()
    if not s:
        return None
    m = re.search(r'\(([\d.]+)%\)', s)
    if m:
        return float(m.group(1))
    m = re.match(r'\+?(\d+)\s*-\s*(\d+)', s)
    if m:
        pos, neg = int(m.group(1)), int(m.group(2))
        return round((pos / (pos + neg)) * 100, 1) if (pos + neg) else 0.0
    m = re.match(r'([\d.]+)\s*/\s*([\d.]+)', s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return round((num / den) * 100, 1) if den else 0.0
    m = re.match(r'^[\d.]+$', s)
    if m:
        return min(float(s), 100.0)
    return None

def normalize_qid(raw_id):
    if isinstance(raw_id, dict):
        return raw_id.get("$oid", str(raw_id))
    return str(raw_id)

def load_students():
    path = os.path.join(DATA_DIR, "student_performance.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    students = {}
    for item in raw:
        sid = item.get("student_id")
        attempts = item.get("attempts", [])
        for a in attempts:
            a["marks_pct"] = normalize_marks(a.get("marks"))
        attempts.sort(key=lambda a: a.get("date", ""))
        students[sid] = attempts
    print(f"[data_loader] Loaded {len(students)} students, {sum(len(v) for v in students.values())} total attempts")
    return students

def load_questions():
    path = os.path.join(DATA_DIR, "question_bank.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    questions = {}
    skipped = 0
    seen_ids = set()
    for q in raw:
        qid = normalize_qid(q.get("_id", ""))
        if qid in seen_ids:
            skipped += 1
            continue
        seen_ids.add(qid)
        if q.get("difficulty") is None:
            skipped += 1
            continue
        qtype = q.get("questionType", "scq")
        content = q.get(qtype) or q.get("scq") or q.get("mcq") or q.get("integerQuestion") or {}
        if not content.get("answer"):
            skipped += 1
            continue
        q["_id_normalized"] = qid
        questions[qid] = q
    print(f"[data_loader] Loaded {len(questions)} questions, skipped {skipped}")
    return questions

def load_dost_config():
    path = os.path.join(DATA_DIR, "dost_config.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        config = {item["type"]: item for item in raw if "type" in item}
    elif isinstance(raw, dict):
        config = raw
    else:
        config = {}
    print(f"[data_loader] Loaded {len(config)} DOST types")
    return config

_cache = {}

def get_all_data():
    if not _cache:
        _cache["students"] = load_students()
        _cache["questions"] = load_questions()
        _cache["dost_config"] = load_dost_config()
    return _cache
