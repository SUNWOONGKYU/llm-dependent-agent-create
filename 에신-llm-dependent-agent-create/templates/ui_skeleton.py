# -*- coding: utf-8 -*-
"""ui.py 뼈대 — 로컬 웹 GUI 서버 (표준 라이브러리만). 에신 V4 templates/ui_skeleton.py

복사해서 app/ui.py 로 두고 「▼ 도메인」 표시 자리만 채운다. 나머지(토큰·포트·terminate_previous·잠금·업로드·작업 락·배경 probe)는 그대로.
원천: 공증 사무 보조 에이전트 ui.py 구성(출입증 토큰 → 쿠키 승격 302, 고정 포트 + SO_EXCLUSIVEADDRUSE, 화면은 마지막 하나만,
경로 탈출 차단, 덮어쓰기 금지, 조용한 종료, favicon 204, 종료 안내) — 도메인 무관 부분만 옮김.

라우트 계약(화면 뼈대 index.html 이 부른다): GET / · /api/status · /api/probe[?live=1] · /api/state · /api/job?id · /api/logs?n · /api/chat/log
  · /api/open-folder?which=output|logs|backups · /api/manual · /api/setup · /api/profile   POST /api/chat · /api/upload · /api/setup/run · /api/profile · (도메인 라우트)
환경변수: UI_ALLOW_MULTI=1(다중 인스턴스 허용) · NO_BROWSER=1(탭 자동 열기 끔)
"""
from __future__ import annotations
import http.server, socketserver, socket, json, os, re, sys, time, uuid, secrets, subprocess, threading, webbrowser, urllib.parse
from email.parser import BytesParser
from email.policy import default as _email_policy
from http import HTTPStatus
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import store, llm, engine, setup_helper  # noqa: E402   ▼ 도메인: 필요한 모듈 추가

UI_DIR = BASE / "ui"
UPLOAD_DIR = BASE / "uploads"; UPLOAD_DIR.mkdir(exist_ok=True)
RUNTIME_DIR = BASE / ".runtime"; RUNTIME_DIR.mkdir(exist_ok=True)
LOCK_FILE = RUNTIME_DIR / "ui.lock"
APP_NAME = "{{에이전트 이름}}"          # ▼ 도메인
APP_SLUG = "{{agent-slug}}"            # ▼ 도메인 — 토큰 폴더 이름(ASCII)
VERSION = "0.1"
PORT = 7700                            # ▼ 도메인 — 에이전트마다 다른 포트
COOKIE = APP_SLUG.replace("-", "_") + "_auth"
MAX_BODY = 64 * 1024 * 1024
INSTANCE = uuid.uuid4().hex


# ---------------------------------------------------------------- 출입증 토큰 (사용자 로컬 폴더에만)
def _token_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / APP_SLUG / "token"


def _load_or_make_token(renew: bool = False) -> str:
    p = _token_path()
    if not renew:
        try:
            t = p.read_text(encoding="ascii").strip()
            if re.fullmatch(r"[A-Za-z0-9_-]{20,64}", t):
                return t
        except Exception:
            pass
    t = secrets.token_urlsafe(24)
    try:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="ascii")
    except Exception:
        pass
    return t


TOKEN = _load_or_make_token("--new-token" in sys.argv)


# ---------------------------------------------------------------- 화면은 마지막 하나만
def _run_ps(script: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        return r.stdout or ""
    except Exception:
        return ""


def _kill_pid(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=12, shell=False)
        return r.returncode == 0
    except Exception:
        return False


def _find_sibling_pids() -> list:
    me = os.getpid(); marker = str(Path(__file__).resolve()).lower()
    out = _run_ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    try:
        data = json.loads(out) if out.strip() else []
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return [int(r.get("ProcessId") or 0) for r in data if r.get("ProcessId") and int(r["ProcessId"]) != me and marker in (r.get("CommandLine") or "").lower()]


def _port_owner(port: int) -> int:
    out = _run_ps(f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess")
    try:
        return int(out.strip())
    except Exception:
        return 0


def _read_lock() -> dict:
    try:
        return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_lock(port: int) -> None:
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "port": port, "instance": INSTANCE, "started": time.time()}), encoding="utf-8")


def terminate_previous() -> int:
    killed = set()
    pid = int(_read_lock().get("pid") or 0)
    if pid and pid != os.getpid() and _kill_pid(pid):
        killed.add(pid)
    for p in _find_sibling_pids():
        if p not in killed and _kill_pid(p):
            killed.add(p)
    owner = _port_owner(PORT)
    if owner and owner != os.getpid() and owner not in killed and _kill_pid(owner):
        killed.add(owner)
    for _ in range(20):
        if _port_owner(PORT) == 0:
            break
        time.sleep(0.15)
    return len(killed)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):   # Windows — 이미 LISTEN 중인 포트 재바인딩 차단
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


# ---------------------------------------------------------------- 배경 작업 (상태를 바꾸는 일은 한 번에 하나)
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_ACTIVE = {"jid": None, "name": ""}
_PROBE = {"cli": None, "running": False}
_CHAT_LOG: list[dict] = []


class Busy(Exception):
    pass


def _job(fn, *a, **kw) -> str:
    jid = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        act = _ACTIVE["jid"]
        if act and _JOBS.get(act, {}).get("status") == "running":
            raise Busy("다른 작업(%s)이 진행 중입니다 — 끝난 뒤 다시 누르세요" % _ACTIVE["name"])
        _JOBS[jid] = {"status": "running", "started": time.time(), "result": None, "error": None, "name": getattr(fn, "__name__", "job")}
        _ACTIVE.update(jid=jid, name=getattr(fn, "__name__", "job"))

    def _run():
        try:
            res = fn(*a, **kw)
            with _JOBS_LOCK:
                _JOBS[jid].update(status="done", result=res)
        except engine.Blocked as e:
            with _JOBS_LOCK:
                _JOBS[jid].update(status="blocked", error=str(e))
        except Exception as e:
            store.log("시스템", "작업 오류: %s" % e, job=jid)
            with _JOBS_LOCK:
                _JOBS[jid].update(status="error", error=llm.human_reason(str(e)) + " (" + str(e)[:120] + ")")
        finally:
            with _JOBS_LOCK:
                if _ACTIVE["jid"] == jid:
                    _ACTIVE.update(jid=None, name="")
    threading.Thread(target=_run, daemon=True).start()
    return jid


def _background_probe():
    """켤 때 LLM 두 자리를 실제로 한 번 불러 본다(설치확인 ≠ 작동확인). 그동안 화면은 「확인하는 중…」."""
    _PROBE["running"] = True
    try:
        _PROBE["cli"] = llm.probe(live=True)
    finally:
        _PROBE["running"] = False


def _slot(c):
    if not c or not c.get("found"):
        return {"found": False, "note": "설치되지 않음"}
    if c.get("live") is not None:
        return {"found": bool(c.get("live")), "note": (c.get("detail") or "") if c.get("live") else "설치됨 · 응답 없음(로그인 확인)"}
    return {"found": None, "note": "확인하는 중…" if _PROBE.get("running") else "확인 못 함 — [상태 새로 고침]"}


def _safe_filename(name: str) -> str:
    name = Path(str(name).replace("\\", "/")).name
    return re.sub(r"[^\w.\-가-힣 ]", "_", name)[:120] or "file"


def _unique(p: Path) -> Path:   # 덮어쓰기 금지
    if not p.exists():
        return p
    stem, suf, i = p.stem, p.suffix, 2
    while (p.with_name("%s(%d)%s" % (stem, i, suf))).exists():
        i += 1
    return p.with_name("%s(%d)%s" % (stem, i, suf))


def _has(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


# ---------------------------------------------------------------- 핸들러
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = APP_SLUG + "/" + VERSION

    def log_message(self, *a):          # 조용히
        pass

    def _authed(self) -> bool:
        return ("%s=%s" % (COOKIE, TOKEN)) in self.headers.get("Cookie", "")

    def _send(self, code: int, body, ctype="application/json; charset=utf-8", extra: dict | None = None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("본문 너무 큼")
        return self.rfile.read(n) if n else b""

    # ---- GET
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/favicon.ico":
            return self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
        if u.path == "/" and q.get("t", [""])[0] == TOKEN:     # 토큰 → 쿠키 승격 → 302
            return self._send(HTTPStatus.FOUND, b"", extra={"Location": "/", "Set-Cookie": "%s=%s; HttpOnly; SameSite=Strict; Path=/" % (COOKIE, TOKEN)})
        if not self._authed():
            return self._send(HTTPStatus.FORBIDDEN, "403 — 이 화면은 시작.bat이 연 주소로만 들어올 수 있습니다. 검은 창의 주소를 다시 여세요.", "text/plain; charset=utf-8")
        if u.path == "/":
            return self._send(HTTPStatus.OK, (UI_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/status":
            try:
                return self._json(200, {"ok": True, **engine.status(), "instance": INSTANCE})
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})
        if u.path == "/api/probe":
            live = q.get("live", ["0"])[0] == "1"
            if live:
                cli = llm.probe(live=True); _PROBE["cli"] = cli; _PROBE["running"] = False
            else:
                cli = _PROBE.get("cli") or llm.probe(live=False)
            llm3 = {"작업": _slot(cli.get("claude")), "1차 검증": _slot(cli.get("claude")), "2차 검증": _slot(cli.get("codex"))}
            # ▼ 도메인: 도구 칩·지식베이스 행·백업 줄. found 는 True/False/None(모름) 세 값 — 모름을 없음으로 적지 않는다
            tools = engine.tool_rows(live) if hasattr(engine, "tool_rows") else []
            kb = engine.kb_rows() if hasattr(engine, "kb_rows") else {}
            backup = {"line": "단계가 바뀔 때마다 · 최근 20개 보관", "detail": "app/state_backups/ — 잘못 초기화됐으면 최신 파일을 state.json 으로 복사"}
            return self._json(200, {"ok": True, "cli": cli, "llm": llm3, "tools": tools, "kb": kb, "backup": backup, "settings": store.load_state().get("settings")})
        if u.path == "/api/state":
            return self._json(200, store.load_state())
        if u.path == "/api/job":
            with _JOBS_LOCK:
                j = _JOBS.get(q.get("id", [""])[0])
            return self._json(200 if j else 404, {"job": j} if j else {"error": "no such job"})
        if u.path == "/api/logs":
            return self._json(200, {"logs": store.recent_logs(int(q.get("n", ["80"])[0]))})
        if u.path == "/api/chat/log":
            return self._json(200, {"log": _CHAT_LOG[-60:]})
        if u.path == "/api/open-folder":
            which = q.get("which", ["output"])[0]
            target = {"output": engine.OUT, "logs": store.LOG_DIR, "backups": store.BACKUP_DIR, "app": BASE}.get(which, engine.OUT)
            try:
                os.startfile(str(target))
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})
            return self._json(200, {"ok": True})
        if u.path == "/api/manual":
            p = BASE.parent / "사용자 매뉴얼(설치 및 사용법).html"
            return self._send(200, p.read_bytes(), "text/html; charset=utf-8") if p.exists() else self._json(404, {"error": "매뉴얼 없음"})
        if u.path == "/api/setup":                                   # 설치 도우미 상태(LLM 두 자리 설치·로그인)
            return self._json(200, setup_helper.상태(_PROBE.get("cli") or llm.probe(live=False)))
        if u.path == "/api/profile":                                 # 설정 블록(우측) + 사용자 기준(좌측 지식베이스) 값
            return self._json(200, {"ok": True, "profile": dict(store.load_config("profile.json", {}), **(store.load_state().get("profile") or {})), "required": getattr(engine, "PROFILE_REQUIRED", [])})
        # ▼ 도메인 GET 라우트
        return self._json(404, {"ok": False, "error": "no route"})

    # ---- POST
    def do_POST(self):
        if not self._authed():
            return self._json(403, {"ok": False, "error": "인증 없음"})
        u = urllib.parse.urlsplit(self.path)
        try:
            return self._post_dispatch(u)
        except Busy as e:
            return self._json(409, {"ok": False, "busy": True, "error": str(e)})

    def _post_dispatch(self, u):
        try:
            if u.path == "/api/upload":
                return self._upload()
            data = json.loads(self._body().decode("utf-8") or "{}")
            if u.path == "/api/chat":
                # 실행형 액션봇: engine.chat(message, confirm) → {reply, action?, needs_confirm?, job?}
                res = engine.chat(data.get("message", ""), bool(data.get("confirm")), _job)
                _CHAT_LOG.append({"q": data.get("message", ""), "a": res.get("reply", ""), "ts": store.now_iso()})
                store.log("AI", (res.get("reply") or "")[:80], action=res.get("action"))
                return self._json(200, {"ok": True, **res})
            if u.path == "/api/setup/run":                           # 설치 도우미 단추 — 표에 박힌 명령만
                return self._json(200, setup_helper.실행(str(data.get("key", ""))))
            if u.path == "/api/profile":                             # 설정·사용자 기준 저장 (state.profile + config/profile.json)
                allowed = set(getattr(engine, "PROFILE_FIELDS", [])) or set(data.keys())
                upd = {k: v for k, v in data.items() if k in allowed}
                store.update_state(lambda s: s.setdefault("profile", {}).update(upd))
                cfg = dict(store.load_config("profile.json", {})); cfg.update(upd); store.save_config("profile.json", cfg)
                store.log("사용자", "설정 저장: %s" % ", ".join(sorted(upd)))
                return self._json(200, {"ok": True, "profile": cfg})
            # ▼ 도메인 POST 라우트 — 상태를 바꾸는 것은 _job(...) 으로, 되돌리기 어려운 것은 needs_confirm 관문
            return self._json(404, {"ok": False, "error": "no route"})
        except Busy:
            raise
        except engine.Blocked as e:
            return self._json(409, {"ok": False, "blocked": True, "error": str(e)})
        except Exception as e:
            store.log("시스템", "요청 오류 %s: %s" % (u.path, e))
            return self._json(500, {"ok": False, "error": llm.human_reason(str(e)), "detail": str(e)[:200]})

    def _upload(self):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self._json(400, {"ok": False, "error": "multipart 필요"})
        raw = self._body()
        msg = BytesParser(policy=_email_policy).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
        saved = []
        for part in msg.iter_parts():
            fname = part.get_filename()
            if not fname:
                continue
            dest = _unique(UPLOAD_DIR / _safe_filename(fname))
            if not str(dest.resolve()).startswith(str(UPLOAD_DIR.resolve())):
                return self._json(403, {"ok": False, "error": "경로 탈출"})
            with open(dest, "wb") as f:
                f.write(part.get_payload(decode=True) or b"")
            saved.append(str(dest))
        store.log("사용자", "자료 업로드 %d건" % len(saved))
        return self._json(200, {"ok": True, "files": saved})


def main():
    if os.environ.get("UI_ALLOW_MULTI") != "1":
        n = terminate_previous()
        if n:
            print("Closed %d previous window server(s)." % n)
    try:
        srv = _Server(("127.0.0.1", PORT), Handler)
    except OSError:
        print("Port %d is already in use. The screen server was NOT started." % PORT)
        print("Most likely it is already running: open http://localhost:%d" % PORT)
        sys.exit(1)
    _write_lock(PORT)
    url = "http://localhost:%d/?t=%s" % (PORT, TOKEN)
    print("%s v%s — http://localhost:%d  (local only)" % (APP_NAME, VERSION, PORT))
    print("Close this window to stop.  브라우저 탭을 닫아도 서버는 살아 있습니다 — 다 쓰셨으면 이 검은 창을 닫으세요.")
    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    threading.Thread(target=_background_probe, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
