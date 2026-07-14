# pip install numpy requests
# Run once from ~/agentic-ai/ to migrate flat files → SQLite
# Original files are NOT deleted — kept as backup

import os
import json
import glob
from memory_db import init_db, save


def migrate():
    init_db()
    counts = {"project": 0, "progress": 0, "lesson": 0, "research": 0}

    # projects.json
    path = "memory/projects.json"
    try:
        with open(path) as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        for item in items:
            if save("personal_projects", "project", json.dumps(item), {"source": "projects.json"}):
                counts["project"] += 1
    except FileNotFoundError:
        print(f"  Skipping {path} — not found")
    except Exception as e:
        print(f"  Warning: {path} failed — {e}")

    # learning_progress.json
    path = "memory/learning_progress.json"
    try:
        with open(path) as f:
            data = json.load(f)
        if save("knowledge_learning", "progress", json.dumps(data), {"source": "learning_progress.json"}):
            counts["progress"] += 1
    except FileNotFoundError:
        print(f"  Skipping {path} — not found")
    except Exception as e:
        print(f"  Warning: {path} failed — {e}")

    # lessons/*.md
    for fpath in sorted(glob.glob("memory/lessons/*.md")):
        try:
            with open(fpath) as f:
                content = f.read()
            fname = os.path.basename(fpath)
            if save("knowledge_learning", "lesson", content, {"filename": fname}):
                counts["lesson"] += 1
            else:
                print(f"  Warning: lesson {fname} failed to save")
        except Exception as e:
            print(f"  Warning: {fpath} — {e}")

    # research/*.md
    for fpath in sorted(glob.glob("memory/research/*.md")):
        try:
            with open(fpath) as f:
                content = f.read()
            fname = os.path.basename(fpath)
            if save("research", "research", content, {"filename": fname}):
                counts["research"] += 1
            else:
                print(f"  Warning: research {fname} failed to save")
        except Exception as e:
            print(f"  Warning: {fpath} — {e}")

    print("\nMigration complete:")
    print(f"  projects migrated:  {counts['project']}")
    print(f"  progress migrated:  {counts['progress']}")
    print(f"  lessons migrated:   {counts['lesson']}")
    print(f"  research migrated:  {counts['research']}")
    total = sum(counts.values())
    print(f"  TOTAL:              {total}")
    print("\nOriginal flat files untouched — check memory/ folder.")


if __name__ == "__main__":
    migrate()
