# -*- coding: utf-8 -*-
"""store.py 뼈대 (에신 V4 templates/store_skeleton.py → app/store.py)
원천: 완성도 높은 실물 에이전트 store — 상태·이력·로그 락 분리, 원자 쓰기, 단계 스냅샷(최근 20), 초기화 백업.
 — state.json·history.json·logs 원자적 쓰기 + 잠금.

부품 출처(BOM 🟢): 공증 사무 보조 에이전트 store.py `_atomic_write_json` + RLock 3종.
- tmp 파일명에 pid·thread id를 넣어 동시 쓰기 lost-update 방지 → os.replace.
- 상태(state)·이력(history)·로그(log)는 각각 다른 락 — 한 락에 몰면 로그 때문에 상태 저장이 밀린다.
"""
from __future__ import annotations
import json, os, shutil, threading, time, datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
STATE_PATH = APP / "state.json"
HISTORY_PATH = APP / "history.json"
LOG_DIR = APP / "logs"
CONFIG_DIR = APP / "config"

_STATE_LOCK = threading.RLock()
_HISTORY_LOCK = threading.RLock()
_LOG_LOCK = threading.Lock()


def _atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.%d.%d.tmp" % (path.name, os.getpid(), threading.get_ident()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # 손상 파일은 옆에 보존하고 기본값으로 — 조용히 덮어쓰지 않는다
        bad = path.with_suffix(path.suffix + ".corrupt.%d" % int(time.time()))
        try:
            os.replace(path, bad)
        except OSError:
            pass
        return default


# ---------------------------------------------------------------- state
def default_state() -> dict:
    """▼ 도메인: 작업 단위의 상태 뼈대. settings 는 사용자 설정(새 시작 후에도 유지)."""
    return {
        "version": 1, "created": now_iso(), "updated": now_iso(),
        "phase": "intake",            # intake → ... → done  (▼ 도메인 단계 이름 = 화면 진행 단계 = 흐름도 번호)
        "intake": {},                 # 사용자가 넣은 것(가명화 전 원문은 넣지 않는다)
        "pseudonym_names": [],        # 가명화 이름 목록(재시작 후 복원)
        "profile": {},                # 사용자 기준(설정 블록)
        "items": {},                  # ▼ 도메인: 작업 단위별 상태 {"1": {"status": "pending", "calls": 0, ...}}
        "blocked": None,              # {"code": "...", "since": iso}
        "settings": {"max_calls": 15, "max_minutes": 30, "length_mode": "full"},   # ▼ 도메인 상한
    }


def load_state() -> dict:
    with _STATE_LOCK:
        st = _read_json(STATE_PATH, None)
        if st is None:
            st = default_state()
            _atomic_write_json(STATE_PATH, st)
        return st


BACKUP_DIR = STATE_PATH.parent / "state_backups"
_PHASE_MARK = {"v": None}


def backup_state(tag: str = "manual") -> Path:
    """state.json 스냅샷 — state_backups/state_{tag}_{ts}.json. 최근 20개만 보관."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / ("state_%s_%s.json" % (tag, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    if STATE_PATH.exists():
        shutil.copy2(STATE_PATH, dst)
    olds = sorted(BACKUP_DIR.glob("state_*.json"), key=lambda p: p.stat().st_mtime)
    for p in olds[:-20]:
        try:
            p.unlink()
        except OSError:
            pass
    return dst


def save_state(st: dict) -> None:
    with _STATE_LOCK:
        # 단계가 바뀔 때마다 직전 상태를 스냅샷 — 덮어쓰기 사고(2026-09-17) 복구용
        if STATE_PATH.exists() and _PHASE_MARK["v"] is not None and st.get("phase") != _PHASE_MARK["v"]:
            backup_state("phase_%s" % _PHASE_MARK["v"])
        _PHASE_MARK["v"] = st.get("phase")
        st["updated"] = now_iso()
        _atomic_write_json(STATE_PATH, st)


def update_state(fn) -> dict:
    """fn(state) -> None. 읽기-수정-쓰기를 한 락 안에서."""
    with _STATE_LOCK:
        st = load_state()
        fn(st)
        save_state(st)
        return st


# ---------------------------------------------------------------- history (호출 집계)
def append_history(entry: dict) -> None:
    with _HISTORY_LOCK:
        h = _read_json(HISTORY_PATH, {"version": 1, "calls": []})
        entry.setdefault("ts", now_iso())
        h["calls"].append(entry)
        _atomic_write_json(HISTORY_PATH, h)


def history_summary() -> dict:
    with _HISTORY_LOCK:
        h = _read_json(HISTORY_PATH, {"calls": []})
    calls = h.get("calls", [])
    return {
        "total_calls": len(calls),
        "by_provider": _count(calls, "provider"),
        "failures": sum(1 for c in calls if not c.get("ok", True)),
    }


def _count(items, key):
    out = {}
    for it in items:
        out[it.get(key, "?")] = out.get(it.get(key, "?"), 0) + 1
    return out


# ---------------------------------------------------------------- log (행위자 구분)
def log(actor: str, message: str, **extra) -> None:
    """actor: '사용자' | '시스템' | 'AI'. 공증 에이전트 ACTOR 규칙 — 누가 한 일인지 구분."""
    LOG_DIR.mkdir(exist_ok=True)
    line = {"ts": now_iso(), "actor": actor, "msg": message}
    if extra:
        line.update(extra)
    with _LOG_LOCK:
        with open(LOG_DIR / ("%s.jsonl" % datetime.date.today().isoformat()), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def recent_logs(n: int = 100) -> list:
    LOG_DIR.mkdir(exist_ok=True)
    files = sorted(LOG_DIR.glob("*.jsonl"))
    out = []
    for fp in files[-2:]:
        with open(fp, encoding="utf-8") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    return out[-n:]


# ---------------------------------------------------------------- config
def load_config(name: str, default: dict | None = None) -> dict:
    return _read_json(CONFIG_DIR / name, default or {})


def save_config(name: str, data: dict) -> None:
    _atomic_write_json(CONFIG_DIR / name, data)


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")
