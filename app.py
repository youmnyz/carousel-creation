import json
import os
import queue
import threading
import uuid
import zipfile

from flask import Flask, Response, jsonify, render_template, request, send_file

import config
import fetcher
import transformer
import carousel

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload-template", methods=["POST"])
def upload_template():
    f = request.files.get("template")
    if not f or not f.filename.lower().endswith(".pptx"):
        return jsonify({"error": "Please upload a .pptx file"}), 400
    uid = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{uid}.pptx")
    f.save(path)
    return jsonify({"template_id": uid, "name": f.filename})


@app.route("/api/posts")
def api_posts():
    url = request.args.get("url", "").strip()
    if url:
        config.WP_SITE_URL = url.rstrip("/")
    try:
        posts = fetcher.get_posts(per_page=50)
        return jsonify([{"id": p["id"], "title": p["title"], "link": p["link"]} for p in posts])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/<filename>")
def download_file(filename):
    safe = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(path):
        return "Not found", 404
    # Strip the uuid__ prefix for the download name shown to user
    display_name = safe.split("__", 1)[-1] if "__" in safe else safe
    return send_file(path, as_attachment=True, download_name=display_name)


@app.route("/api/download-zip")
def download_zip():
    files = request.args.get("files", "")
    if not files:
        return "No files specified", 400
    names = [os.path.basename(n) for n in files.split(",") if n.strip()]
    zip_id = str(uuid.uuid4())
    zip_path = os.path.join(UPLOAD_DIR, f"{zip_id}__carousels.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            path = os.path.join(UPLOAD_DIR, name)
            if os.path.exists(path):
                arcname = name.split("__", 1)[-1] if "__" in name else name
                zf.write(path, arcname)
    return send_file(zip_path, as_attachment=True, download_name="carousels.zip")


@app.route("/api/process", methods=["POST"])
def api_process():
    body = request.get_json(force=True)
    selected_ids = set(int(i) for i in body.get("post_ids", []))
    template_id  = body.get("template_id", "").strip()
    blog_url     = body.get("blog_url", "").strip()
    api_key      = body.get("api_key", "").strip()

    if not selected_ids:
        return jsonify({"error": "No posts selected."}), 400
    if not template_id:
        return jsonify({"error": "No template uploaded."}), 400
    if not api_key:
        return jsonify({"error": "Anthropic API key is required."}), 400

    template_path = os.path.join(UPLOAD_DIR, f"{template_id}.pptx")
    if not os.path.exists(template_path):
        return jsonify({"error": "Template not found. Please re-upload."}), 400

    if blog_url:
        config.WP_SITE_URL = blog_url.rstrip("/")
    config.ANTHROPIC_API_KEY = api_key
    config.TEMPLATE_FILE = template_path
    transformer._client = None  # reset so it picks up the new key

    q = queue.Queue()

    def run():
        generated = []
        try:
            posts = fetcher.get_posts(per_page=50)
            posts = [p for p in posts if p["id"] in selected_ids]
            total = len(posts)
            q.put({"type": "info", "msg": f"Processing {total} post(s)..."})

            for i, post in enumerate(posts, 1):
                q.put({"type": "progress",
                       "msg": f"[{i}/{total}] Transforming: {post['title']}",
                       "current": i, "total": total})
                try:
                    data = transformer.transform(post)
                    slug = post["link"].rstrip("/").split("/")[-1]
                    file_id = str(uuid.uuid4())
                    filename = f"{file_id}__{slug}-carousel.pptx"
                    out_path = os.path.join(UPLOAD_DIR, filename)
                    carousel.build_carousel(post, data, out_path)
                    generated.append(filename)
                    q.put({"type": "done_one",
                           "msg": f"✓ {post['title']}",
                           "filename": filename})
                except Exception as e:
                    q.put({"type": "error", "msg": f"✗ {post['title']}: {e}"})

            q.put({"type": "complete",
                   "msg": f"Done. {len(generated)} carousel(s) ready to download.",
                   "zip_param": ",".join(generated)})
        except Exception as e:
            q.put({"type": "error", "msg": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def stream():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
