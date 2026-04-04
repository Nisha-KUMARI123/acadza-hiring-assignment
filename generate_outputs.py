"""
generate_outputs.py
Run this AFTER starting the FastAPI server with:
    uvicorn main:app --reload

This script calls /analyze and /recommend for all students
and saves results to sample_outputs/
"""

import json
import os
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = "sample_outputs"


def get_student_ids():
    """Fetch student list from the leaderboard endpoint."""
    try:
        resp = requests.get(f"{BASE_URL}/leaderboard", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return [entry["student_id"] for entry in data["leaderboard"]]
    except Exception as e:
        print(f"[ERROR] Could not reach server: {e}")
        print("Make sure FastAPI is running: uvicorn main:app --reload")
        sys.exit(1)


def save_json(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    student_ids = get_student_ids()
    print(f"\nFound {len(student_ids)} students: {student_ids}\n")

    all_failed = []

    for sid in student_ids:
        print(f"Processing {sid}...")

        # ── Analyze ──
        try:
            resp = requests.post(f"{BASE_URL}/analyze/{sid}", timeout=10)
            resp.raise_for_status()
            analyze_data = resp.json()
            save_json(f"{OUTPUT_DIR}/{sid}_analyze.json", analyze_data)
        except Exception as e:
            print(f"  [WARN] analyze failed for {sid}: {e}")
            all_failed.append((sid, "analyze"))

        # ── Recommend ──
        try:
            resp = requests.post(f"{BASE_URL}/recommend/{sid}", timeout=10)
            resp.raise_for_status()
            recommend_data = resp.json()
            save_json(f"{OUTPUT_DIR}/{sid}_recommend.json", recommend_data)
        except Exception as e:
            print(f"  [WARN] recommend failed for {sid}: {e}")
            all_failed.append((sid, "recommend"))

    print(f"\n✓ Done. Outputs saved to ./{OUTPUT_DIR}/")
    if all_failed:
        print(f"[WARN] Failed: {all_failed}")
    else:
        print("All students processed successfully.")


if __name__ == "__main__":
    main()