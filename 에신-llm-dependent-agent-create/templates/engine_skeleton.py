# -*- coding: utf-8 -*-
"""engine.py 뼈대 (에신 V4 templates/engine_skeleton.py → app/engine.py)

State Machine(무판단 스케줄러 — 다음에 무엇을 실행할지 결정론으로 정함) + 액션봇(LLM — 판단이 있는 단계) 합작.
ui_skeleton.py 가 부르는 계약:  Blocked · status() · chat(message, confirm, job_fn) · tool_rows(live) · kb_rows() · OUT
run.py 가 부르는 계약:          start()/intake(...) · run_all() · resume() · status()
▼ 도메인 자리만 채운다. 단계 이름은 화면 진행 단계·흐름도 번호와 같아야 한다.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
import store, llm, guard

APP = Path(__file__).resolve().parent
OUT = APP / "output"; OUT.mkdir(exist_ok=True)


class Blocked(Exception):
    """사람 문장으로 된 차단 사유. ui 는 409 로, run.py 는 '차단:' 으로 보여 준다."""


# 설정 블록(우측)·사용자 기준(좌측 지식베이스) 필드 — ui_skeleton /api/profile 이 이 목록만 저장한다
PROFILE_FIELDS = ["sender_name"]            # ▼ 도메인
PROFILE_REQUIRED = []                       # ▼ 도메인: 비어 있으면 좌측 지식베이스 「기준」 접기를 펼친다

# 작업 단위 패턴 — 둘 중 하나를 고른다(시범 제조에서 드러난 분기, 2026-09-17)
#   SINGLE: 한 번에 하나(논문처럼 길고 큰 작업). intake 가 이전 상태를 백업 후 초기화한다.
#   MULTI : 여러 건을 순차 처리하고 이력을 누적(회의록·문서 정리처럼 짧은 작업). intake 는 items 에 항목을 추가하고 state["current"] 만 잠근다.
WORK_MODE = "SINGLE"                        # ▼ 도메인: "SINGLE" | "MULTI"


# ---------------------------------------------------------------- 가명화 이름(재시작 후 복원)
_NAMES: list[str] = []


def _names_from_fields() -> list[str]:
    """새 입력 경로를 추가하면 여기 등록(빠뜨리면 실명이 샌다)."""
    if not _NAMES:
        _NAMES.extend(store.load_state().get("pseudonym_names") or [])
    return list(_NAMES)


def _limits(st):
    se = st.get("settings", {})
    return int(se.get("max_calls", 15)), float(se.get("max_minutes", 30))


# ---------------------------------------------------------------- 시작(intake) — 상태를 지우는 유일한 경로: 확인 + 백업
def intake(*required, names: list[str] | None = None, profile: dict | None = None, force: bool = False, **fields) -> dict:
    missing = [k for k, v in fields.items() if k in required and not (str(v or "")).strip()]
    if missing:
        raise Blocked("입력 필수 항목 부족: %s" % ", ".join(missing))
    prev = store.load_state()
    if WORK_MODE == "MULTI":
        # 이력 누적: 진행 중(current)이 있으면 잠금, 없으면 새 항목을 items 에 추가한다. 이전 항목은 지우지 않는다.
        cur = prev.get("current")
        if cur and (prev.get("items") or {}).get(cur, {}).get("status") not in (None, "done", "stalled") and not force:
            raise Blocked("진행 중인 {{작업 단위}}(%s)이 있습니다. 끝내거나 force=True." % cur)
        item_id = store.now_iso().replace(":", "").replace("-", "")[:15]

        def _add(st):
            st.setdefault("items", {})[item_id] = {"status": "pending", "calls": 0, "created": store.now_iso(), **{k: v for k, v in fields.items() if k != "names"}}
            st["current"] = item_id
            st["pseudonym_names"] = sorted(set((st.get("pseudonym_names") or []) + list(names or [])))
            st["profile"] = dict(st.get("profile") or {}, **(profile or {}))
            st["phase"] = "{{첫 단계 이름}}"
        st = store.update_state(_add)
        _NAMES.clear(); _NAMES.extend(st["pseudonym_names"])
        store.log("시스템", "{{작업 단위}} 추가 — %s" % item_id)
        return st
    if prev.get("items") and not force:
        raise Blocked("이미 진행 중인 {{작업 단위}}(%d건)이 있습니다. 새로 시작하면 현재 상태가 백업된 뒤 초기화됩니다 — 확인 후 force=True." % len(prev["items"]))
    if prev.get("items"):
        store.log("시스템", "새 시작 전 상태 백업 — %s" % store.backup_state("before_intake").name)

    def _set(st):
        keep = dict(st.get("settings") or {})
        st.clear(); st.update(store.default_state()); st["settings"].update(keep)
        st["intake"] = {k: v for k, v in fields.items() if k != "names"}
        st["profile"] = dict(store.load_config("profile.json", {}), **(profile or {}))
        st["pseudonym_names"] = list(names or [])
        st["phase"] = "{{첫 단계 이름}}"
    st = store.update_state(_set)
    _NAMES.clear(); _NAMES.extend(names or [])
    store.log("시스템", "{{작업 단위}} 시작 — %s" % json.dumps(fields, ensure_ascii=False)[:60])
    return st


# ---------------------------------------------------------------- 자율 루프 (▼ 도메인)
def run_all(progress=None) -> dict:
    """단계 순서대로 끝까지. 각 단계 체크포인트. 상한 도달 단계는 건너뛰고 계속(보고에 남김). 이어쓰기: 중단된 단계는 기존 산출물에서 재개."""
    st = store.load_state()
    if st.get("blocked"):
        raise Blocked("차단 상태: %s" % st["blocked"]["code"])
    # ▼ 도메인: 단계 함수들을 순서대로. 최소 골격 —
    #   draft = _call_llm(prompt, "draft")            # 작업(Claude)
    #   v1 = verify_1st(draft["text"], rubric)        # 1차 검증(Claude 별도 호출) → 미달이면 수정 ≤ N회
    #   v2 = verify_2nd(draft["text"], rubric)        # 2차 검증(Codex) → 결과를 item["verify2"] 에 저장, 화면에 표시
    #   [사람 승인] → 최종 산출물 → OUT
    raise NotImplementedError("▼ 도메인: 단계 함수들을 여기서 순서대로 부른다 — verify_1st·verify_2nd 를 반드시 호출한다")


def resume() -> dict:
    return run_all()


def verify_1st(draft: str, rubric: str) -> dict:
    """1차 검증 — 작업(초고)을 만든 호출과 **별도 프로세스**의 Claude 가 본다(자기 것을 자기가 통과시키지 않게). 반환 {ok, data:{pass, issues[]}}"""
    return llm.call_json("\n".join(["너는 검증자다. 작성자가 아니다.", "# 기준\n" + rubric, "# 대상\n" + draft,
                                     '# 출력 — JSON 하나만: {"pass": true|false, "issues": ["..."]}']), purpose="verify1", timeout=300, providers=["claude"])


def verify_2nd(draft: str, rubric: str) -> dict:
    """2차 검증 — 다른 회사 AI(Codex). 없으면 Claude 로 폴백하되 결과에 provider 를 남긴다. 화면 「2차 검증」 칩은 설치·로그인 확인일 뿐 — 이 함수가 불려야 «실제로 검증됨»이다."""
    return llm.call_json("\n".join(["You are an independent verifier, not the author.", "# Criteria\n" + rubric, "# Target\n" + draft,
                                     '# Output — exactly one JSON: {"pass": true|false, "issues": ["..."]}']), purpose="verify2", timeout=300, providers=["codex", "claude"])


def _call_llm(prompt: str, purpose: str, timeout: int = 300) -> dict:
    """LLM 호출 전 가명화 → 후 복원. 실명이 프롬프트에 남으면 전송 중단(fail-closed)."""
    masked, mapping = guard.pseudonymize(prompt, _names_from_fields())
    leak = guard.scan_leak(masked)
    if leak:
        raise Blocked("가명화 후에도 개인정보 패턴 잔존: %s — 전송 중단" % leak)
    r = llm.call(masked, purpose=purpose, timeout=timeout)
    if r["ok"]:
        r["text"] = guard.restore(r["text"], mapping)
    return r


# ---------------------------------------------------------------- 화면 계약
def status() -> dict:
    st = store.load_state()
    return {"phase": st.get("phase"), "blocked": st.get("blocked"), "items": st.get("items", {}), "history": store.history_summary()}


def tool_rows(live: bool = False) -> list:
    """좌측 「도구」 칩. found 는 True/False/None(모름). ▼ 도메인"""
    import importlib.util
    def has(m): return importlib.util.find_spec(m) is not None
    return [
        {"label": "{{도구 1}}", "desc": "{{무엇을}}", "found": has("{{모듈}}"), "note": "" if has("{{모듈}}") else "없으면 {{대신 사람이 할 일}} — pip install {{모듈}}"},
    ]


def kb_rows() -> dict:
    """좌측 「지식베이스」 ①~④ + 작업 지식. id 는 gui_skeleton 의 div id."""
    st = store.load_state()
    return {
        "kb-inject-row": {"label": "① 직접 주입", "desc": "규칙 {{N}}종 — 프롬프트에 그대로 넣습니다", "found": True, "note": "app/skills/*.md"},
        "kb-rag-row": {"label": "② RAG", "desc": "올린 자료에서 찾아서 넣습니다", "found": bool((st.get("intake") or {}).get("files")), "note": ""},
        "kb-api-row": {"label": "③ API", "desc": "{{외부 조회 또는 해당 없음}}", "found": None, "note": ""},
        "kb-mcp-row": {"label": "④ MCP", "desc": "이 에이전트에는 MCP 연결이 없습니다", "found": None, "note": "해당 없음"},
        "kb-experience-row": {"label": "작업 지식", "desc": "{{누적되는 것}}", "found": bool(st.get("items")), "note": ""},
    }


# ---------------------------------------------------------------- 액션봇(실행형) — 화이트리스트 액션 + 되돌리기 어려운 것은 needs_confirm
_ACTIONS = {
    "status": {"irreversible": False, "desc": "진행 상태 조회"},
    "run_all": {"irreversible": False, "desc": "끝까지 진행"},
    # "export": {"irreversible": True, "desc": "최종 산출물 생성"},   ▼ 도메인
}


def chat(message: str, confirm: bool, job_fn) -> dict:
    """메시지 → LLM 에 의도 파악(JSON: {action, args, reply}) → 화이트리스트 액션 실행. 비가역이면 confirm 전까지 needs_confirm."""
    prompt = "\n".join([
        "너는 「{{에이전트 이름}}」 안의 AI 다. 사용자의 말을 읽고 (a) 실행할 액션이 있으면 아래 목록에서 하나 고르고 (b) 한 문장으로 답한다.",
        "액션 목록: " + json.dumps({k: v["desc"] for k, v in _ACTIONS.items()}, ensure_ascii=False),
        "출력 — JSON 하나만: {\"action\": \"이름 또는 null\", \"args\": {}, \"reply\": \"한 문장\"}",
        "사용자: " + message,
    ])
    r = llm.call_json(prompt, purpose="chat", timeout=120)
    if not r["ok"]:
        return {"reply": "지금은 답하지 못했습니다: " + llm.human_reason(r["error"] or "")}
    d = r["data"] or {}; act = d.get("action")
    if not act or act not in _ACTIONS:
        return {"reply": d.get("reply") or "알겠습니다."}
    if _ACTIONS[act]["irreversible"] and not confirm:
        return {"reply": d.get("reply") or "", "action": act, "args": d.get("args") or {}, "needs_confirm": True,
                "message": "되돌리기 어려운 작업입니다: %s — 진행할까요?" % _ACTIONS[act]["desc"]}
    if act == "status":
        return {"reply": json.dumps(status(), ensure_ascii=False)[:400], "action": act}
    if act == "run_all":
        return {"reply": "끝까지 진행합니다.", "action": act, "job": job_fn(run_all)}
    return {"reply": "알겠습니다.", "action": act}
