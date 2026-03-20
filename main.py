import json
import os
import sys
from datetime import datetime

import config
import fetcher
import transformer
import carousel

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"processed_ids": []}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def output_path(slug: str) -> str:
    folder = config.OUTPUT_FOLDER
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{slug}-carousel.pptx")


def run():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting blog-to-carousel...")

    try:
        config.validate()
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    state = load_state()
    processed = set(state["processed_ids"])

    print(f"Fetching posts from {config.WP_SITE_URL}...")
    try:
        posts = fetcher.get_posts(per_page=20)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    new_posts = [p for p in posts if p["id"] not in processed]
    print(f"Found {len(posts)} posts, {len(new_posts)} new to process.")

    if not new_posts:
        print("Nothing to do. All posts already processed.")
        return

    success = 0
    for post in new_posts:
        print(f"\n  Processing: \"{post['title']}\" (ID {post['id']})")
        try:
            print("    [>] Transforming with Claude...")
            carousel_data = transformer.transform(post)

            out = output_path(post["slug"])
            print(f"    [>] Generating carousel -> {out}")
            carousel.build_carousel(post, carousel_data, out)

            state["processed_ids"].append(post["id"])
            save_state(state)
            success += 1
            print(f"    [OK] Done: {out}")

        except json.JSONDecodeError as e:
            print(f"    [FAIL] Failed to parse Claude response: {e}")
        except Exception as e:
            print(f"    [FAIL] Error processing post {post['id']}: {e}")

    print(f"\nDone. {success}/{len(new_posts)} carousels generated.")


if __name__ == "__main__":
    run()
