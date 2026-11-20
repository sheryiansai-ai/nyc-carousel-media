#!/usr/bin/env python3
"""NYC Poster: our own small Instagram scheduler.

It runs every 5 minutes as a GitHub Action in sheryiansai-ai/nyc-carousel-media. It publishes
every post in queue/ whose publish_at time has come, through Instagram's official Graph API.

A queue file (queue/<anything>.json) looks like this:
  {
    "publish_at": "2026-11-21T10:00:00+05:30",
    "type": "carousel",               // carousel | image | story | reel
    "media": ["https://.../s-01.png", "https://.../s-02.png"],   // public URLs, in order
    "caption": "text, links, #tags",  // ignored for stories
    "by": "cloud-bot"                  // who queued it (for the status page)
  }

After a publish attempt:
  - success: the file moves to queue/done/ with "result": {"media_id", "permalink", "published_at"}
  - failure: "attempts" and "last_error" are added; after 3 tries it moves to queue/failed/

Secrets (repository settings > Secrets and variables > Actions):
  IG_TOKEN    a Page access token with instagram_basic and instagram_content_publish
  IG_USER_ID  the Instagram professional account id (the "instagram_business_account" id)

Env: DRY_RUN=1 makes no Instagram calls (to test the queue). CHECK_ONLY=1 only checks the token and quota.
GRAPH_VERSION overrides the API version.
"""
import datetime as dt
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue")
REPO = os.environ.get("GITHUB_REPOSITORY", "sheryiansai-ai/nyc-carousel-media")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
GRAPH = "https://graph.facebook.com/" + os.environ.get("GRAPH_VERSION", "v24.0")
TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER = os.environ.get("IG_USER_ID", "")
DRY = os.environ.get("DRY_RUN") == "1"
MAX_ATTEMPTS = 3
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now():
    return dt.datetime.now(dt.timezone.utc)


def log(*a):
    print(now().astimezone(IST).strftime("%H:%M:%S"), *a, flush=True)


# ---------- Instagram Graph API ----------

def api(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    req = urllib.request.Request(url + ("?" + data.decode() if method == "GET" else ""),
                                 data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body)["error"]
            body = f'{msg.get("message")} (code {msg.get("code")}, subcode {msg.get("error_subcode")})'
        except Exception:
            pass
        raise RuntimeError(f"Instagram API {path}: {body}") from None


def wait_ready(container, timeout=600):
    """Containers are processed by Instagram before they can be published (videos take longest)."""
    t0 = time.time()
    while True:
        st = api("GET", container, fields="status_code,status")
        code = st.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container}: {code} {st.get('status', '')}")
        if time.time() - t0 > timeout:
            raise RuntimeError(f"container {container}: still {code} after {timeout}s")
        time.sleep(5)


def create(**params):
    return api("POST", f"{IG_USER}/media", **params)["id"]


def publish(post, urls):
    kind = post["type"]
    caption = post.get("caption", "")
    if kind == "image":
        c = create(image_url=urls[0], caption=caption)
    elif kind == "carousel":
        if not 2 <= len(urls) <= 10:
            raise RuntimeError(f"a carousel needs 2 to 10 items, got {len(urls)}")
        kids = []
        for u in urls:
            k = create(**({"video_url": u, "media_type": "VIDEO"} if u.lower().endswith((".mp4", ".mov"))
                          else {"image_url": u}), is_carousel_item="true")
            kids.append(k)
        for k in kids:
            wait_ready(k)
        c = create(media_type="CAROUSEL", children=",".join(kids), caption=caption)
    elif kind == "story":
        u = urls[0]
        c = create(media_type="STORIES", **({"video_url": u} if u.lower().endswith((".mp4", ".mov")) else {"image_url": u}))
    elif kind == "reel":
        c = create(media_type="REELS", video_url=urls[0], caption=caption, share_to_feed="true")
    else:
        raise RuntimeError(f"unknown type {kind!r}")
    wait_ready(c)
    media_id = api("POST", f"{IG_USER}/media_publish", creation_id=c)["id"]
    try:
        link = api("GET", media_id, fields="permalink").get("permalink", "")
    except Exception:
        link = ""
    return {"media_id": media_id, "permalink": link}


# ---------- media: Instagram only takes JPEG images from a public URL ----------

def as_public_jpegs(post_id, urls):
    """PNG/WebP slides are converted to JPEG, committed under queue/media/<id>/ and served from raw GitHub."""
    from PIL import Image
    out, changed = [], False
    folder = os.path.join(QUEUE, "media", post_id)
    for i, u in enumerate(urls, 1):
        low = u.lower().split("?")[0]
        if low.endswith((".jpg", ".jpeg", ".mp4", ".mov")):
            out.append(u)
            continue
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, f"{i:02d}.jpg")
        if not os.path.exists(dest):
            with urllib.request.urlopen(u, timeout=60) as r:
                im = Image.open(io.BytesIO(r.read())).convert("RGB")
            im.save(dest, "JPEG", quality=92, optimize=True, progressive=True)
            changed = True
        rel = os.path.relpath(dest, ROOT).replace(os.sep, "/")
        out.append(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{rel}")
    return out, changed


def wait_public(urls, timeout=180):
    t0 = time.time()
    for u in urls:
        while True:
            try:
                with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=20) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            if time.time() - t0 > timeout:
                raise RuntimeError(f"not public yet: {u}")
            time.sleep(5)


# ---------- git ----------

def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[-300:]}")
    return r


def push(message):
    paths = [x for x in ("queue", "STATUS.md") if os.path.exists(os.path.join(ROOT, x))]
    if not paths:
        return
    git("add", "-A", *paths)
    if not git("diff", "--cached", "--quiet", check=False).returncode:
        return  # nothing to commit
    git("commit", "-m", message)
    for _ in range(5):
        if git("push", "origin", f"HEAD:{BRANCH}", check=False).returncode == 0:
            return
        git("pull", "--rebase", "origin", BRANCH, check=False)
    raise RuntimeError("push failed 5 times")


# ---------- queue ----------

def due_files():
    files = sorted(f for f in glob.glob(os.path.join(QUEUE, "*.json")))
    due = []
    for f in files:
        try:
            p = json.load(open(f))
            at = dt.datetime.fromisoformat(p["publish_at"])
            if at.tzinfo is None:
                at = at.replace(tzinfo=IST)
        except Exception as e:
            log(f"skip {os.path.basename(f)}: unreadable ({e})")
            continue
        if at <= now():
            due.append((at, f, p))
    return sorted(due)


def move(f, sub, post):
    os.makedirs(os.path.join(QUEUE, sub), exist_ok=True)
    dest = os.path.join(QUEUE, sub, os.path.basename(f))
    json.dump(post, open(dest, "w"), indent=1, ensure_ascii=False)
    os.remove(f)


def status_page():
    def rows(pattern, limit, reverse):
        items = []
        for f in glob.glob(pattern):
            try:
                items.append(json.load(open(f)))
            except Exception:
                pass
        items.sort(key=lambda p: p.get("publish_at", ""), reverse=reverse)
        return items[:limit]

    def line(p, extra):
        cap = (p.get("caption") or "").split("\n")[0][:70].replace("|", "/")
        return f"| {p.get('publish_at', '')[:16].replace('T', ' ')} | {p.get('type', '')} | {cap} | {extra} |"

    out = ["# NYC Poster: Instagram queue", "", "Times are IST. This page changes only when the queue changes.", "",
           "## Coming up", "", "| When | Type | First line | Note |", "|---|---|---|---|"]
    out += [line(p, ("retry " + str(p.get("attempts")) + ": " + p.get("last_error", "")[:80]) if p.get("attempts") else "")
            for p in rows(os.path.join(QUEUE, "*.json"), 30, False)]
    out += ["", "## Published", "", "| When | Type | First line | Link |", "|---|---|---|---|"]
    out += [line(p, p.get("result", {}).get("permalink", "")) for p in rows(os.path.join(QUEUE, "done", "*.json"), 30, True)]
    out += ["", "## Failed (3 tries)", "", "| When | Type | First line | Error |", "|---|---|---|---|"]
    out += [line(p, p.get("last_error", "")[:120]) for p in rows(os.path.join(QUEUE, "failed", "*.json"), 15, True)]
    open(os.path.join(ROOT, "STATUS.md"), "w").write("\n".join(out) + "\n")


def check():
    """Read-only: proves the token and account id work, and shows today's publishing quota. Posts nothing."""
    me = api("GET", IG_USER, fields="username,name,media_count")
    q = api("GET", f"{IG_USER}/content_publishing_limit", fields="quota_usage,config").get("data", [{}])[0]
    cfg = q.get("config", {})
    log(f"OK: @{me.get('username')} ({me.get('name')}), {me.get('media_count')} posts on the account")
    log(f"publishing quota: {q.get('quota_usage')} used of {cfg.get('quota_total')} per {cfg.get('quota_duration', 86400) // 3600} hours")


def main():
    if not DRY and not (TOKEN and IG_USER):
        log("Not set up yet: add the IG_TOKEN and IG_USER_ID secrets (see SETUP.md). Nothing was published.")
        return  # exit cleanly, so the 5-minute runs don't fail before setup
    if os.environ.get("CHECK_ONLY") == "1":
        check()
        return
    due = due_files()
    log(f"{len(due)} post(s) due")
    for at, f, post in due:
        name = os.path.basename(f)
        post_id = os.path.splitext(name)[0]
        if post.get("claimed_at"):
            # An earlier run started this one and never finished: it may already be on Instagram.
            # Never risk a double post: park it in failed/ for a human to check.
            post["last_error"] = ("An earlier run started publishing this at " + post["claimed_at"] +
                                  " and did not finish. Check Instagram before queueing it again.")
            move(f, "failed", post)
            log(f"PARKED {name}: unfinished earlier attempt")
            if not DRY:
                status_page(); push(f"poster: parked {post_id}")
            continue
        try:
            if post.get("type") not in ("carousel", "image", "story", "reel") or not post.get("media"):
                raise RuntimeError("needs a type (carousel/image/story/reel) and at least one media URL")
            urls, changed = as_public_jpegs(post_id, post["media"])
            if DRY:
                log(f"DRY RUN {name}: would publish {post['type']} with {len(urls)} item(s): {urls[0]}")
                continue
            # Claim it (and push the JPEGs) before calling Instagram, so a crash can never lead to a repeat.
            post["claimed_at"] = now().astimezone(IST).isoformat(timespec="seconds")
            json.dump(post, open(f, "w"), indent=1, ensure_ascii=False)
            push(f"poster: publishing {post_id}")
            if changed:
                wait_public(urls)
            result = publish(post, urls)
            post.pop("claimed_at", None)
            post["result"] = {**result, "published_at": now().astimezone(IST).isoformat(timespec="minutes")}
            move(f, "done", post)
            log(f"published {name}: {result['permalink']}")
        except Exception as e:
            post.pop("claimed_at", None)  # Instagram refused it, so it is safe to try again
            post["attempts"] = post.get("attempts", 0) + 1
            post["last_error"] = str(e)[:500]
            log(f"FAILED {name} (try {post['attempts']}): {e}")
            if post["attempts"] >= MAX_ATTEMPTS:
                move(f, "failed", post)
            else:
                json.dump(post, open(f, "w"), indent=1, ensure_ascii=False)
        if not DRY:
            status_page()
            push(f"poster: {post_id}")
    if not DRY:
        status_page()
        push("poster: queue page")  # commits only if the queue changed


if __name__ == "__main__":
    main()
