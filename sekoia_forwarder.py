#!/usr/bin/env python3
import json
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional

import requests
import typer
from requests.adapters import HTTPAdapter, Retry
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

app = typer.Typer()

# ————————————————————————————————
# Configuration
# ————————————————————————————————

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "tenants.json"

try:
    tenants = json.loads(CONFIG_FILE.read_text())
    TENANT_KEYS = {t["name"]: t["intake_key"] for t in tenants if "intake_key" in t}
except Exception as e:
    typer.echo(typer.style(f"⚠️ Failed to load tenants.json: {e}", fg="red"))
    TENANT_KEYS = {}

TEST_URL           = "https://intake.test.sekoia.io/batch"
PROD_URL           = "https://intake.sekoia.io/batch"
DEFAULT_CHUNK_SIZE = 1000
TIME_BETWEEN_CHUNKS = 1  # seconds

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))


# ————————————————————————————————
# Helpers
# ————————————————————————————————

def chunk_events(events: List[Any], chunk_size: int):
    chunk: List[Any] = []
    for evt in events:
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
        chunk.append(evt)
    if chunk:
        yield chunk

def send_events(intake_key: str, events: List[Dict[str, Any]], prod: bool, chunk_size: int):
    url    = PROD_URL if prod else TEST_URL
    params = {"return_response": "true"}
    sent_ids: List[str] = []

    for idx, chunk in enumerate(chunk_events(events, chunk_size)):
        typer.echo(f"→ Sending chunk #{idx} ({len(chunk)} events)")
        payload = {"intake_key": intake_key, "jsons": [json.dumps(e) for e in chunk]}
        resp = session.post(url, json=payload, params=params)
        if not resp.ok:
            typer.echo(typer.style(f"   ✖ Error {resp.status_code}: {resp.text}", fg="red"))
        else:
            sent_ids += resp.json().get("event_ids", [])
        sleep(TIME_BETWEEN_CHUNKS)

    if sent_ids:
        typer.echo(typer.style(f"✔ Sent event IDs: {', '.join(sent_ids)}", fg="green"))


# ————————————————————————————————
# File-watch handler
# ————————————————————————————————

class TailHandler(FileSystemEventHandler):
    def __init__(self, prod: bool, chunk_size: int):
        self.prod       = prod
        self.chunk_size = chunk_size
        self.positions: Dict[str, int] = {}

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".log"):
            return

        path = event.src_path
        pos  = self.positions.get(path, 0)
        with open(path, "r") as f:
            f.seek(pos)
            lines = f.readlines()
            self.positions[path] = f.tell()

        # group by tenant
        buckets: Dict[str, List[Dict[str,Any]]] = {}
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                typer.echo(typer.style(f"Skipped invalid JSON: {raw}", fg="yellow"))
                continue
            tenant = obj.get("tenant")
            if not tenant:
                typer.echo(typer.style(f"No tenant field in: {obj}", fg="yellow"))
                continue
            buckets.setdefault(tenant, []).append(obj)

        for tenant, evts in buckets.items():
            key = TENANT_KEYS.get(tenant)
            if not key:
                typer.echo(typer.style(f"⚠️ No key for tenant '{tenant}', skipping {len(evts)} events", fg="red"))
                continue
            send_events(key, evts, self.prod, self.chunk_size)


# ————————————————————————————————
# Main callback (no subcommand)
# ————————————————————————————————

@app.callback(invoke_without_command=True)
def main(
    prod: bool = typer.Option(False, "--prod", help="Use the production endpoint"),
    chunk_size: int = typer.Option(DEFAULT_CHUNK_SIZE, "--chunk-size", help="Events per batch"),
):
    """
    Watch all *.log under logs/sekoia and forward JSON events to Sekoia using each event’s tenant key.
    """
    log_dir = Path("logs") / "sekoia"
    log_dir.mkdir(parents=True, exist_ok=True)
    files = list(log_dir.glob("*.log"))

    typer.echo(f"Watching {len(files)} log files in {log_dir}:")
    for f in files:
        typer.echo(f"  • {f}")

    handler  = TailHandler(prod, chunk_size)
    observer = Observer()
    observer.schedule(handler, str(log_dir), recursive=False)
    observer.start()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    app()

