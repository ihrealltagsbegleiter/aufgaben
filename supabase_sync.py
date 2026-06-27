#!/usr/bin/env python3
"""Liest pending-todos.json und schreibt neue Einträge in Supabase."""
import json, time, subprocess, os, sys
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Secrets-Check: Laut abbrechen statt still scheitern
if not SUPABASE_URL:
    print("❌ FEHLER: SUPABASE_URL nicht gesetzt (GitHub Secret fehlt?)")
    sys.exit(1)
if not SUPABASE_KEY:
    print("❌ FEHLER: SUPABASE_ANON_KEY nicht gesetzt (GitHub Secret fehlt?)")
    sys.exit(1)

print(f"🔗 Supabase: {SUPABASE_URL}")

def curl_get(url):
    r = subprocess.run([
        "curl", "-sf",
        "-H", f"apikey: {SUPABASE_KEY}",
        "-H", f"Authorization: Bearer {SUPABASE_KEY}",
        url
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"⚠️  curl GET fehlgeschlagen (code {r.returncode}): {r.stderr}")
        return []
    return json.loads(r.stdout) if r.stdout.strip() else []

def curl_post(data):
    r = subprocess.run([
        "curl", "-sf", "-X", "POST",
        "-H", f"apikey: {SUPABASE_KEY}",
        "-H", f"Authorization: Bearer {SUPABASE_KEY}",
        "-H", "Content-Type: application/json",
        "-H", "Prefer: return=minimal",
        "-d", json.dumps(data),
        f"{SUPABASE_URL}/rest/v1/tasks"
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⚠️  curl POST fehlgeschlagen (code {r.returncode}): {r.stderr}")
    return r.returncode == 0

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
    print(f"❌ {errors} Fehler — Supabase-URL/Key prüfen!")
    sys.exit(1)
