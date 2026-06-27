#!/usr/bin/env python3
"""Liest pending-todos.json und schreibt neue Einträge in Supabase.
Nutzt SERVICE_ROLE_KEY (umgeht RLS) wenn gesetzt, sonst ANON_KEY.
"""
import json, time, subprocess, os, sys
from datetime import datetime, timezone

_DEFAULT_URL = "https://cuukfowezhcosjnuckuo.supabase.co"

SUPABASE_URL = os.environ.get("SUPABASE_URL", _DEFAULT_URL).rstrip("/")

# Service Role Key hat Vorrang (umgeht RLS), Fallback: Anon Key
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", "")

if SERVICE_KEY:
    SUPABASE_KEY = SERVICE_KEY
    print("🔑 Nutze Service Role Key (RLS-Bypass)")
elif ANON_KEY and not ANON_KEY.startswith("eyJ"):
    SUPABASE_KEY = ANON_KEY
    print("🔑 Nutze ANON_KEY (sb_publishable Format)")
else:
    # Fallback auf App-Key — dieser schlägt wegen RLS fehl, aber besser als gar nichts
    SUPABASE_KEY = "sb_publishable_Cj33uDp4shZaiWYbJkRPqQ_usXXCUcz"
    print("⚠️  Kein Service Role Key gesetzt → INSERT wird wegen RLS scheitern!")
    print("   Lösung: SUPABASE_SERVICE_ROLE_KEY als GitHub Secret hinterlegen")
    print("   (Supabase Dashboard → Settings → API → service_role key)")

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
print(f"🔗 Supabase: {SUPABASE_URL}")


def curl_request(method, url, data=None):
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
        print(f"⚠️  GET → HTTP {status}: {body}")
        return []
    try:
        return json.loads(body) if body else []
    except Exception as e:
        print(f"⚠️  Parse-Fehler: {e}")
        return []


def curl_post(data):
    status, body = curl_request("POST", f"{SUPABASE_URL}/rest/v1/tasks", data)
    if status not in (200, 201):
        print(f"  ⚠️  POST → HTTP {status}: {body}")
        return False
    return True


todos = json.loads(open("pending-todos.json").read())
if not todos:
    print("ℹ️  Keine neuen ToDos.")
    sys.exit(0)

print(f"📋 {len(todos)} ToDo(s) gefunden, lade bestehende...")
rows = curl_get(f"{SUPABASE_URL}/rest/v1/tasks?select=data")
existing = set()
for row in rows:
    d = row.get("data", {})
    if isinstance(d, str):
        try: d = json.loads(d)
        except: continue
    if d.get("title"):
        existing.add(d["title"].lower().strip())
print(f"   {len(existing)} bestehende Aufgaben.")

inserted = 0
errors   = 0

for title in todos:
    if title.lower().strip() in existing:
        print(f"⏭ Duplikat: {title}")
        continue
    time.sleep(0.5)
    ts  = int(time.time() * 1000)
    tid = f"T{ts}"
    ok  = curl_post({
        "id": tid,
        "data": {
            "id": tid, "due": None, "frog": False, "note": "📥 Via Plaud",
            "dread": None, "eisen": 2, "title": title, "effort": "s",
            "energy": "low", "impact": 1, "context": "quick", 
            "horizon": None, "due_time": None, "projectId": None,
            "recurDays": None, "recurring": None
        },
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    if ok:
        print(f"✅ {title}")
        existing.add(title.lower().strip())
        inserted += 1
    else:
        print(f"❌ {title}")
        errors += 1

print(f"\n{'='*40}")
print(f"✅ {inserted} neue Aufgabe(n) eingetragen.")
if errors:
    print(f"❌ {errors} Fehler")
    sys.exit(1)
