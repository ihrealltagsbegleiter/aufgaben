#!/usr/bin/env python3
"""
Plaud → Aufgaben Sync
Holt täglich neue Plaud-Aufnahmen, extrahiert ToDos aus den KI-Notizen
und schreibt sie in die Supabase tasks-Tabelle (Eingang).
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timezone, timedelta

PLAUD_TOKEN   = os.environ["PLAUD_TOKEN"]
SUPABASE_URL  = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY  = os.environ["SUPABASE_ANON_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

PLAUD_HEADERS = {
    "Authorization": f"Bearer {PLAUD_TOKEN}",
    "Content-Type": "application/json"
}

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def get_plaud_files():
    """Aufnahmen der letzten 24h von Plaud holen."""
    url = "https://api.plaud.ai/api/v1/files"
    params = {"date_from": YESTERDAY, "date_to": TODAY, "page_size": 100}
    r = requests.get(url, headers=PLAUD_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def get_plaud_notes(file_id):
    """KI-Notizen einer Aufnahme abrufen."""
    url = f"https://api.plaud.ai/api/v1/files/{file_id}/notes"
    r = requests.get(url, headers=PLAUD_HEADERS, timeout=30)
    if r.status_code != 200:
        return ""
    data = r.json()
    # Inhalt aus erstem Eintrag extrahieren
    if isinstance(data, list) and data:
        return data[0].get("data_content", "")
    return ""


def extract_todos(text):
    """
    Extrahiert Checkbox-ToDos aus Markdown-Text.
    Erkennt: '- [ ] Text', '* [ ] Text', '[ ] Text'
    """
    todos = []
    pattern = re.compile(r'[-*]?\s*\[\s*\]\s+(.+)', re.MULTILINE)
    for match in pattern.finditer(text):
        todo = match.group(1).strip()
        # Plaud-interne Marker entfernen (@Name, -[TBD])
        todo = re.sub(r'@\w+\s*', '', todo).strip()
        todo = re.sub(r'\s*-\s*\[TBD\]$', '', todo).strip()
        if todo:
            todos.append(todo)
    return todos


def get_existing_titles():
    """Bereits vorhandene Aufgaben-Titel aus Supabase laden (Duplikat-Schutz)."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tasks?select=data",
        headers=SUPABASE_HEADERS,
        timeout=30
    )
    if r.status_code != 200:
        return set()
    titles = set()
    for row in r.json():
        d = row.get("data", {})
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except Exception:
                continue
        t = d.get("title", "")
        if t:
            titles.add(t.lower().strip())
    return titles


def make_task(title):
    """Erstellt ein task-Objekt im Format der Aufgaben-App."""
    ts = int(time.time() * 1000)
    task_id = f"T{ts}"
    return {
        "id": task_id,
        "data": {
            "id": task_id,
            "due": None,
            "frog": False,
            "note": "📥 Via Plaud importiert",
            "dread": None,
            "eisen": 2,          # wichtig, nicht dringend (Eingang-Standard)
            "title": title,
            "effort": "s",
            "energy": "low",
            "impact": 1,
            "context": "quick",
            "created": TODAY,
            "horizon": "today",
            "due_time": None,
            "projectId": None,
            "recurDays": None,
            "recurring": None
        },
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


def insert_task(task):
    """Task in Supabase einfügen."""
    payload = {
        "id": task["id"],
        "data": task["data"],
        "updated_at": task["updated_at"]
    }
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/tasks",
        headers=SUPABASE_HEADERS,
        json=payload,
        timeout=30
    )
    return r.status_code in (200, 201)


def main():
    print(f"🔍 Plaud-Aufnahmen vom {YESTERDAY} bis {TODAY} abrufen...")
    files = get_plaud_files()
    print(f"   {len(files)} Aufnahmen gefunden.")

    existing = get_existing_titles()
    print(f"   {len(existing)} bestehende Aufgaben geladen (Duplikat-Schutz).")

    new_count = 0
    skip_count = 0

    for f in files:
        file_id = f.get("id")
        name = f.get("name", file_id)
        notes = get_plaud_notes(file_id)
        if not notes:
            continue

        todos = extract_todos(notes)
        if not todos:
            continue

        print(f"\n📋 {name}: {len(todos)} ToDo(s) gefunden")
        for todo in todos:
            if todo.lower().strip() in existing:
                print(f"   ⏭ Duplikat: {todo}")
                skip_count += 1
                continue

            task = make_task(todo)
            # Kurze Pause damit IDs eindeutig bleiben
            time.sleep(2)
            task = make_task(todo)

            if insert_task(task):
                print(f"   ✅ Eingefügt: {todo}")
                existing.add(todo.lower().strip())
                new_count += 1
            else:
                print(f"   ❌ Fehler bei: {todo}")

    print(f"\n{'='*40}")
    print(f"✅ {new_count} neue Aufgabe(n) eingefügt")
    print(f"⏭ {skip_count} Duplikat(e) übersprungen")


if __name__ == "__main__":
    main()
