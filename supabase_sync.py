#!/usr/bin/env python3
"""Liest pending-todos.json und schreibt neue Einträge in Supabase."""
import json, time, subprocess, os, sys
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Secrets-Check
if not SUPABASE_URL:
    print("❌ FEHLER: SUPABASE_URL nicht gesetzt (GitHub Secret fehlt?)")
    sys.exit(1)
if not SUPABASE_KEY:
    print("❌ FEHLER: SUPABASE_ANON_KEY nicht gesetzt (GitHub Secret fehlt?)")
    sys.exit(1)

print(f"🔗 Supabase: {SUPABASE_URL}")


def curl_request(method, url, data=None):
    """HTTP-Request mit vollständiger Fehlerausgabe (Body + Status)."""
    cmd = [
        "curl", "-s", "-w", "\nHTTP_STATUS:%{http_code}",
        "-H", f"apikey: {SUPABASE_KEY}",
        "-H", f"Authorization: Bearer {SUPABASE_KEY}",
    ]
    if method == "POST":
        cmd += ["-X", "POST",
                "-H", "Content-Type: application/json",
                "-H", "Prefer: return=minimal",
                "-d", json.dumps(data)]
    cmd.append(url)

    r = subprocess.run(cmd, capture_output=True, text=True)
    parts = r.stdout.rsplit("\nHTTP_STATUS:", 1)
    body   = parts[0].strip() if parts else ""
    status = int(parts[1].strip()) if len(parts) > 1 else 0

    return status, body


def curl_get(url):
    status, body = curl_request("GET", url)
    if status != 200:
        print(f"⚠️  GET {url} → HTTP {status}: {body}")
        return []
    try:
        return json.loads(body) if body else []
    except Exception as e:
        print(f"⚠️  JSON-Parse-Fehler: {e} | Body: {body[:200]}")
        return []


def curl_post(data):
    status, body = curl_request("POST", f"{SUPABASE_URL}/rest/v1/tasks", data)
    if status not in (200, 201):
        print(f"  ⚠️  POST → HTTP {status}: {body}")
        return False
    return True


todos = json.loads(open("pending-todos.json").read())
if not todos:
    print("ℹ️  Keine neuen ToDos in pending-todos.json.")
    sys.exit(0)

print(f"📋 {len(todos)} ToDo(s) gefunden, prüfe gegen bestehende Aufgaben...")

rows = curl_get(f"{SUPABASE_URL}/rest/v1/tasks?select=data")
existing = set()
for row in rows:
    d = row.get("data", {})
    if isinstance(d, str):
        try: d = json.loads(d)
        except: continue
    if d.get("title"):
        existing.add(d["title"].lower().strip())

print(f"   {len(existing)} bestehende Aufgaben geladen.")

inserted = 0
errors = 0

for title in todos:
    if title.lower().strip() in existing:
        print(f"⏭ Duplikat: {title}")
        continue
    time.sleep(0.6)
    ts = int(time.time() * 1000)
    tid = f"T{ts}"
    ok = curl_post({
        "id": tid,
        "data": {
            "id": tid, "due": None, "frog": False, "note": "📥 Via Plaud",
            "dread": None, "eisen": 2, "title": title, "effort": "s",
            "energy": "low", "impact": 1, "context": "quick", "created": TODAY,
            "horizon": "today", "due_time": None, "projectId": None,
            "recurDays": None, "recurring": None
        },
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    if ok:
        print(f"✅ {title}")
        existing.add(title.lower().strip())
        inserted += 1
    else:
        print(f"❌ Fehler beim Einfügen: {title}")
        errors += 1

print(f"\n{'='*40}")
print(f"✅ {inserted} neue Aufgabe(n) eingetragen.")
if errors:
    print(f"❌ {errors} Fehler — siehe HTTP-Fehlermeldungen oben!")
    sys.exit(1)
