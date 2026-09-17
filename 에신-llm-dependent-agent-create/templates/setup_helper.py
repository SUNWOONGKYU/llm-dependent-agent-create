# -*- coding: utf-8 -*-
"""setup_helper.py 뼈대 — 비개발자가 LLM 두 자리(Claude Code · Codex) 설치·로그인을 화면 단추로 끝내게 한다.
에신 V4 templates/setup_helper.py → app/setup_helper.py

kind 는 셋뿐: "url"(브라우저로 연다) · "shell"(새 콘솔 창에 명령 — 사람이 보는 앞에서) · "pip"(같은 파이썬의 pip).
cmd 는 리스트(shell=True 금지). 설치 «페이지»가 아니라 Windows 내장 설치기(winget)로 설치 창을 띄운다 — 받아서 실행까지 시키지 않는다.
필수 순서: 1 Claude 설치 → 2 Claude 로그인 → 3 Codex 설치 → 4 Codex 로그인 → [다시 확인]. 2차 검증(Codex)을 빠뜨리면 있는 기능에 입구가 없는 것.
"""
import subprocess, sys, webbrowser

명령표: dict[str, dict] = {
    "claude_install": {"order": 1, "title": "Claude Code 설치 창 열기", "kind": "shell",
        "cmd": ["cmd", "/c", "start", "", "cmd", "/k", "winget", "install", "--id", "Anthropic.ClaudeCode", "-e", "--accept-package-agreements", "--accept-source-agreements"],
        "why": "{{판단·작성·1차 검증}}을 맡는 LLM 입니다.",
        "after": "검은 창에서 설치가 끝나면 2번 [로그인 창 열기]를 누르십시오. 「winget 을 찾을 수 없다」면 https://claude.com/claude-code 에서 받아 설치하십시오."},
    "claude_login": {"order": 2, "title": "Claude 로그인 창 열기", "kind": "shell",
        "cmd": ["cmd", "/c", "start", "", "cmd", "/k", "claude"],
        "why": "검은 창이 열리고 로그인 안내가 나옵니다. 쓰시는 Claude 계정으로 로그인하시면 됩니다.",
        "after": "로그인을 마치셨으면 그 창을 닫고 [다시 확인]을 누르십시오."},
    "codex_install": {"order": 3, "title": "Codex 설치 창 열기", "kind": "shell",
        "cmd": ["cmd", "/c", "start", "", "cmd", "/k", "winget", "install", "--id", "OpenAI.Codex", "-e", "--accept-package-agreements", "--accept-source-agreements"],
        "why": "결과를 한 번 더 검증하는 두 번째 LLM 입니다(다른 회사 제품 · Codex).",
        "after": "설치가 끝나면 4번 [Codex 로그인 창 열기]를 누르십시오."},
    "codex_login": {"order": 4, "title": "Codex 로그인 창 열기", "kind": "shell",
        "cmd": ["cmd", "/c", "start", "", "cmd", "/k", "codex", "login"],
        "why": "ChatGPT 계정으로 로그인하시면 됩니다.",
        "after": "로그인을 마치셨으면 그 창을 닫고 [다시 확인]을 누르십시오."},
    # ▼ 도메인: 선택 도구 (예) "pypdf": {"order": 10, "title": "PDF 판독 설치", "kind": "pip", "pkg": "pypdf", "why": "...", "after": "..."}
}


def 명령목록() -> list:
    return sorted(명령표, key=lambda k: 명령표[k]["order"])


def 상태(probe: dict) -> dict:
    """probe = llm.probe(live=True) 결과. {"필수":[{key,title,done,why,after}], "다됐나": bool|None}"""
    cl, cx = probe.get("claude") or {}, probe.get("codex") or {}
    rows = []
    for key in 명령목록():
        d = 명령표[key]
        if key.startswith("claude"):
            done = bool(cl.get("found")) if key.endswith("install") else cl.get("live")
        elif key.startswith("codex"):
            done = bool(cx.get("found")) if key.endswith("install") else cx.get("live")
        else:
            done = None
        rows.append({"key": key, "title": d["title"], "done": done, "why": d["why"], "after": d["after"]})
    musts = [r for r in rows if r["key"].startswith(("claude", "codex"))]
    다됐나 = None if any(r["done"] is None for r in musts) else all(r["done"] for r in musts)
    return {"필수": rows, "다됐나": 다됐나}


def 실행(key: str) -> dict:
    """표에 박힌 명령만 돌린다 — 사용자 입력이 명령이 되는 길은 없다."""
    d = 명령표.get(key)
    if not d:
        return {"ok": False, "error": "허용되지 않은 항목"}
    try:
        if d["kind"] == "url":
            webbrowser.open(d["url"]); return {"ok": True, "did": "브라우저에서 열었습니다: " + d["url"]}
        if d["kind"] == "shell":
            subprocess.Popen(d["cmd"]); return {"ok": True, "did": "새 창을 열었습니다. " + d["after"]}
        if d["kind"] == "pip":
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", sys.executable, "-m", "pip", "install", d["pkg"]]); return {"ok": True, "did": "설치 창을 열었습니다. " + d["after"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "알 수 없는 kind"}
