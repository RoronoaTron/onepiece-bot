"""Archivio su file JSON nel repository (cartella data/).
Lo storico (history.jsonl) è append-only: i record non vengono mai sovrascritti né cancellati."""
import json
import os

DATA = os.environ.get("ONEPIECE_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _p(name):
    return os.path.join(DATA, name)


def load(name, default):
    try:
        with open(_p(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    tmp = _p(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _p(name))


def history_append(rec):
    os.makedirs(DATA, exist_ok=True)
    with open(_p("history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def history_read(code=None):
    try:
        with open(_p("history.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if code is None or rec.get("set") == code:
                    yield rec
    except FileNotFoundError:
        return
