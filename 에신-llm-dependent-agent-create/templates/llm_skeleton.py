# -*- coding: utf-8 -*-
"""llm.py 뼈대 (에신 V4 templates/llm_skeleton.py → app/llm.py) — 구독 CLI 두 자리(claude→codex), API 키 0, 격리 cwd, 파일 리다이렉션, probe(설치≠작동), call_json(정확히 1개 JSON).
원본 설명: — 구독 CLI 호출 채널 (claude → codex 두 자리). LLM API 키 0.

부품 출처(BOM 🟡): 공증 사무 보조 에이전트 engine.py — `_sub_env`(🟢), `_probe_cli`, `_CleanCwd`,
`_run_via_tempfiles`(Windows 파이프 핸들 상속 우회), `call_llm` 재시도 3회, `call_codex` stdin 전달.
재단: 폴백 2단(claude·codex), 법령 MCP probe 제거, 도구 0 고정(검색은 코드가 한다), 모델은 config.

원칙
- 제작·런타임 모두 구독. `_sub_env()`가 API 키 5종을 지운다 — "API 키 미사용" 약속을 코드가 지킨다.
- 설치 확인 ≠ 작동 확인. `probe(live=True)`는 "reply OK" 실호출로 작동을 본다(준비 상태 패널용).
- 매 호출 새 빈 폴더(cwd)에서 — 작업 트리·세션 기억 계층으로 값이 새지 않게.
"""
from __future__ import annotations
import os, shutil, subprocess, tempfile, time, json
from pathlib import Path
from typing import Optional

try:
    from . import store  # type: ignore
except ImportError:  # 단독 실행
    import store  # type: ignore

_API_KEYS = ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_AUTH_TOKEN",
             "OPENAI_API_KEY", "CODEX_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY")
_CLAUDE_NO_TOOLS = ["--tools", "", "--disallowedTools", "mcp__*"]
RETRY_ATTEMPTS = 3
RETRY_DELAY_S = 2

DEFAULTS = {
    "order": ["claude", "codex"],          # 두 자리뿐 — 다른 CLI 를 끼워 넣지 않는다(PO 2026-09-17)
    "codex_model": "gpt-5.6-terra",      # sol은 도구 호스트 장애 실측(2026-09-17) — 텍스트 생성엔 무관하나 안전한 쪽
    "claude_model": None,                 # None = CLI 기본
    "timeout": 300,
}


def _cfg() -> dict:
    c = dict(DEFAULTS)
    c.update(store.load_config("llm.json", {}))
    return c


def _sub_env() -> dict:
    env = dict(os.environ)
    for k in _API_KEYS:
        env.pop(k, None)
    env.setdefault("PYTHONUTF8", "1")
    return env


class _CleanCwd:
    """호출마다 새 빈 폴더. 실패 시 공용 temp로 물러나지 않고 예외."""
    def __init__(self, prefix: str):
        self.prefix = prefix
        self.path: Optional[str] = None

    def __enter__(self) -> str:
        last = None
        for base in (tempfile.gettempdir(), str(Path.home())):
            try:
                self.path = tempfile.mkdtemp(prefix=self.prefix, dir=base)
                return self.path
            except OSError as e:
                last = e
        raise RuntimeError("격리 폴더 생성 실패: %s" % last)

    def __exit__(self, *a):
        if self.path:
            shutil.rmtree(self.path, ignore_errors=True)


class _Result:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _run(argv: list, input_text: str, env: dict, cwd: str, timeout: int) -> _Result:
    """실제 사용 함수 — run()의 CompletedProcess를 보존한다."""
    out_fd, out_path = tempfile.mkstemp(prefix="llm_out_", suffix=".txt", dir=cwd)
    err_fd, err_path = tempfile.mkstemp(prefix="llm_err_", suffix=".txt", dir=cwd)
    in_fd, in_path = tempfile.mkstemp(prefix="llm_in_", suffix=".txt", dir=cwd)
    os.close(out_fd); os.close(err_fd); os.close(in_fd)
    with open(in_path, "w", encoding="utf-8") as f:
        f.write(input_text)
    argv = [x.replace("__PROMPT_FILE__", in_path) if isinstance(x, str) else x for x in argv]
    with open(in_path, "rb") as fin, open(out_path, "wb") as fout, open(err_path, "wb") as ferr:
        cp = subprocess.run(argv, stdin=fin, stdout=fout, stderr=ferr, env=env, cwd=cwd,
                            timeout=timeout, shell=False, check=False)
    return _Result(cp.returncode, _read(out_path), _read(err_path))


def _read(p: str) -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _which(name: str) -> str:
    for cand in (name, name + ".cmd", name + ".exe"):
        p = shutil.which(cand)
        if p:
            return str(Path(p).resolve())
    return ""


def _argv(provider: str, cfg: dict) -> list:
    exe = _which(provider)
    if not exe:
        return []
    if provider == "claude":
        a = [exe, "-p", "--output-format", "text"] + _CLAUDE_NO_TOOLS
        if cfg.get("claude_model"):
            a += ["--model", cfg["claude_model"]]
        return a
    if provider == "codex":
        a = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only"]
        if cfg.get("codex_model"):
            a += ["-m", cfg["codex_model"]]
        return a
    return []


# ---------------------------------------------------------------- probe
def probe(live: bool = False, timeout: int = 60) -> dict:
    """{'claude': {found, path, version, live: None|True|False, detail}, 'codex': ...}
    live=True면 'reply OK' 실호출 1회 — 설치 확인 ≠ 작동 확인."""
    cfg = _cfg()
    out = {}
    for name in ("claude", "codex"):
        exe = _which(name)
        rec = {"found": bool(exe), "path": exe, "version": "", "live": None, "detail": ""}
        if exe:
            try:
                with _CleanCwd("probe_") as cwd:
                    cp = _run([exe, "--version"], "", _sub_env(), cwd, 15)
                rec["version"] = ((cp.stdout or cp.stderr).strip().splitlines() or [""])[0][:80]
            except Exception as e:  # 버전 실패는 무해
                rec["detail"] = "version: %s" % e
            if live:
                r = _call_one(name, "Reply with exactly: OK", timeout, cfg)
                rec["live"] = bool(r["ok"] and "OK" in r["text"].upper())
                rec["detail"] = r["error"] or ("%d ms" % r["latency_ms"])
        out[name] = rec
    return out


# ---------------------------------------------------------------- call
def _call_one(provider: str, prompt: str, timeout: int, cfg: dict) -> dict:
    argv = _argv(provider, cfg)
    if not argv:
        return {"ok": False, "text": "", "provider": provider, "latency_ms": 0, "error": "%s CLI 미발견" % provider}
    errors, total = [], 0
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        t0 = time.monotonic()
        try:
            with _CleanCwd("%s_call_" % provider) as cwd:
                cp = _run(argv, prompt, _sub_env(), cwd, timeout)
            ms = int((time.monotonic() - t0) * 1000); total += ms
            if cp.returncode == 0 and (cp.stdout or "").strip():
                return {"ok": True, "text": _strip_noise(cp.stdout), "provider": provider, "latency_ms": ms, "error": None}
            errors.append("%s %d/%d 종료코드 %d: %s" % (provider, attempt, RETRY_ATTEMPTS, cp.returncode, (cp.stderr or "").strip()[:300]))
        except subprocess.TimeoutExpired:
            total += int((time.monotonic() - t0) * 1000)
            errors.append("%s %d/%d 시간 초과(%ds)" % (provider, attempt, RETRY_ATTEMPTS, timeout))
        except Exception as e:
            total += int((time.monotonic() - t0) * 1000)
            errors.append("%s %d/%d 호출 예외: %s" % (provider, attempt, RETRY_ATTEMPTS, e))
        if attempt < RETRY_ATTEMPTS:
            time.sleep(RETRY_DELAY_S)
    return {"ok": False, "text": "", "provider": provider, "latency_ms": total, "error": " / ".join(errors)}


def _strip_noise(text: str) -> str:
    """codex exec가 붙이는 'tokens used' 꼬리 등 제거."""
    lines = [ln for ln in text.splitlines() if not ln.startswith(("hook:", "warning:")) and ln.strip() != "tokens used"]
    # codex: 마지막에 숫자만 있는 줄(토큰 수)
    while lines and lines[-1].strip().replace(",", "").isdigit():
        lines.pop()
    return "\n".join(lines).strip()


def call(prompt: str, timeout: Optional[int] = None, purpose: str = "", providers: Optional[list] = None) -> dict:
    """폴백 체인 호출. 반환 {'ok','text','provider','latency_ms','error','attempts':[...]}. 예외 없음."""
    cfg = _cfg()
    timeout = timeout or cfg["timeout"]
    attempts = []
    for provider in providers or cfg["order"]:
        r = _call_one(provider, prompt, timeout, cfg)
        attempts.append({"provider": provider, "ok": r["ok"], "latency_ms": r["latency_ms"], "error": r["error"]})
        store.append_history({"provider": provider, "ok": r["ok"], "latency_ms": r["latency_ms"], "purpose": purpose,
                              "prompt_chars": len(prompt), "error": (r["error"] or "")[:200]})
        if r["ok"]:
            r["attempts"] = attempts
            return r
    return {"ok": False, "text": "", "provider": None, "latency_ms": sum(a["latency_ms"] for a in attempts),
            "error": " | ".join(a["error"] or "" for a in attempts), "attempts": attempts}


def call_json(prompt: str, **kw) -> dict:
    """JSON 하나만 허용 — 앞뒤 설명문은 허용, 0개·2개 이상·잘린 값은 실패(fail-closed)."""
    r = call(prompt, **kw)
    if not r["ok"]:
        return {"ok": False, "data": None, "error": r["error"], "provider": r["provider"]}
    data, err = extract_single_json(r["text"])
    return {"ok": data is not None, "data": data, "error": err, "provider": r["provider"], "raw": r["text"]}


def extract_single_json(text: str):
    """전체 파싱 우선 → 실패 시 raw_decode로 정확히 하나의 완전한 객체만."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        return json.loads(t), None
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    found = []
    i = 0
    while i < len(t):
        j = t.find("{", i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(t[j:])
            found.append(obj); i = j + end
        except json.JSONDecodeError:
            i = j + 1
    if len(found) == 1:
        return found[0], None
    return None, "JSON 객체 %d개 발견(정확히 1개 필요)" % len(found)


def human_reason(err: str) -> str:
    """내부 오류 → 사용자용 한 문장 (공증 _human_reason 🟢). 원문은 로그에."""
    e = (err or "").strip()
    if not e:
        return "사유를 확인하지 못했습니다."
    if "시간 초과" in e:
        return "응답이 제한 시간 안에 오지 않았습니다."
    if "미발견" in e:
        return "AI 프로그램(CLI)을 찾지 못했습니다. 준비 상태 패널을 확인하세요."
    if "usage limit" in e.lower() or "quota" in e.lower() or "429" in e:
        return "AI 사용 한도에 도달했습니다. 시간이 지난 뒤 재개하세요."
    if "JSON" in e:
        return "AI 응답을 읽지 못했습니다(형식 오류)."
    if "종료코드" in e or "예외" in e:
        return "AI 프로그램이 정상적으로 끝나지 않았습니다."
    return "AI 호출을 마치지 못했습니다."
