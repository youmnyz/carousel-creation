import json
import anthropic
import config

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are a social media content strategist.
Transform blog posts into exactly 6 carousel slide content for Instagram/LinkedIn.
Return ONLY valid JSON — no markdown, no explanation, just the JSON object.

CRITICAL: Text is placed inside circle shapes on slides. Space is extremely limited.
You MUST respect the character limits below — exceeding them causes text to overflow the circle.

Required JSON schema:
{
  "title": "max 40 characters",
  "hook": "max 70 characters",
  "point_1_headline": "max 35 characters",
  "point_1_body": "2-3 bullet points separated by \\n, each starting with • , max 40 chars per bullet",
  "point_2_headline": "max 35 characters",
  "point_2_body": "2-3 bullet points separated by \\n, each starting with • , max 40 chars per bullet",
  "point_3_headline": "max 35 characters",
  "point_3_body": "2-3 bullet points separated by \\n, each starting with • , max 40 chars per bullet",
  "point_4_headline": "max 35 characters",
  "point_4_body": "2-3 bullet points separated by \\n, each starting with • , max 40 chars per bullet",
  "conclusion": "max 100 characters"
}

Rules:
- HARD character limits above — count every character including spaces, do not exceed them
- Headlines: punchy, bold, no filler words
- Body: 2-3 bullet points (• ), each on its own line (separated by \n), max 40 chars each
- Hook: one sentence, bold claim or curiosity gap
- Conclusion: strong CTA or takeaway, not a summary
- All text must be original rewrites, not direct quotes from the blog"""


def transform(post: dict) -> dict:
    """Send a blog post to Claude and get structured 6-slide carousel JSON back."""
    prompt = f"""Blog post title: {post['title']}
Blog post URL: {post['link']}

Blog content:
{post['content'][:8000]}

Transform this into 6-slide carousel content following the schema exactly."""

    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
