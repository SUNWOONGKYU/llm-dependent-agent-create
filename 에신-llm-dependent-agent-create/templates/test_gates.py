# -*- coding: utf-8 -*-
"""시험 뼈대 — 에신 V4 templates/test_gates.py → _개발자료/tests/test_gates.py

최소 시험 건수(docs/40 시험 규격). 규모별 하한: S 20 · M 60 · L 150 건. 이 파일은 그 뼈대 — 도메인 가드를 채운다.
실행: set PYTHONUTF8=1 && python -m pytest _개발자료/tests -q -p no:cacheprovider
원칙: ① 상태를 쓰는 함수는 임시 state 로만 ② «글자가 근처에 있는가» 시험 금지(함수 본문·라우트 경계로 자른다)
      ③ 새 시험은 일부러 망가뜨려 빨간불이 나는지 본 뒤 넣는다(작성자 수동 1회) ④ 미확인 ≠ 통과 ⑤ skip 뼈대·항진명제를 출하본에 남기지 않는다(test_no_skeleton_skips_left, docs/40 §3)
주의: test_output_filter_blocks_forbidden_claims 2건은 모든 {{ }} 를 같은 더미값으로 치환하면 실패가
      정상이다(금지문구=치환문구). 코드 결함 아님 — 도메인 값(금지문구≠치환문구)을 채우면 통과. docs/40 §3
"""
import io, json, os, re, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]          # 에이전트 폴더
APP = ROOT / "app"
TRACK = "gui"          # ▼ 도메인: "gui" | "cli" | "web" — plan.md §1 트랙과 같게. cli 트랙은 GUI 시험을 건너뛴다
SCALE = "S"            # ▼ 도메인: "S" | "M" | "L" — plan.md §1 규모. 시험 하한 S 20 / M 60 / L 150 을 test_scale_minimum 이 강제한다
MIN_TESTS = {"S": 20, "M": 60, "L": 150}
gui = pytest.mark.skipif(TRACK != "gui", reason="GUI 트랙 아님")
sys.path.insert(0, str(APP))
os.environ["PYTHONUTF8"] = "1"


# ───────────────────────────── 0. 진입점·패키징
@gui
def test_start_bat_ascii_crlf_nobom():
    b = (ROOT / "시작.bat").read_bytes()
    assert b[:3] != b"\xef\xbb\xbf", "BOM 있음"
    assert b"\r\n" in b, "CRLF 아님"
    assert all(c < 128 for c in b), "시작.bat 에 비ASCII 문자"
    assert b"python app\\ui.py" in b or b"python app/ui.py" in b


@gui
def test_start_bat_no_paren_blocks():
    # cmd 괄호 블록 안의 echo 는 문구의 괄호로 블록이 조기 종료된다(2026-09-17 실사고). 뼈대는 goto 로 짠다 — 괄호 블록 자체를 금지
    for ln in (ROOT / "시작.bat").read_text(encoding="ascii").splitlines():
        low = ln.strip().lower()
        if "echo" in low and ("(" in ln or ")" in ln):
            pytest.fail("echo 가 있는 줄에 괄호: " + ln)
        if low.startswith("if ") and low.rstrip().endswith("("):
            pytest.fail("괄호 블록 사용 — goto 로 바꿀 것: " + ln)


def test_compile_all():
    for p in APP.glob("*.py"):
        subprocess.run([sys.executable, "-m", "py_compile", str(p)], check=True)


def test_no_secrets_in_tree():
    pat = re.compile(r"AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}")
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".md", ".html", ".json", ".txt", ".bat", ".ps1"} and "_qc" not in p.parts:
            assert not pat.search(p.read_text(encoding="utf-8", errors="ignore")), p


@gui
def test_ui_binds_loopback_only():
    src = (APP / "ui.py").read_text(encoding="utf-8")
    assert '("127.0.0.1", PORT)' in src and "0.0.0.0" not in src


# ───────────────────────────── 1. LLM 두 자리 · API 키 0
def test_llm_two_slots_only():
    import llm
    assert llm.DEFAULTS["order"] == ["claude", "codex"]


def test_no_api_key_env_passthrough():
    import llm
    env = llm._sub_env()
    assert not any(k.endswith("_API_KEY") for k in env), "API 키가 자식 프로세스로 넘어감"


# ───────────────────────────── 2. 화면 계약 (uicontract)
def _js_functions(html: str) -> set:
    return set(re.findall(r"function\s+([A-Za-z_]\w*)\s*\(", html)) | set(re.findall(r"(?:const|let)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(", html))


@gui
def test_uicontract_renderers_and_elements_exist():
    import uicontract
    html = (APP / "ui" / "index.html").read_text(encoding="utf-8")
    fns = _js_functions(html)
    for table in (uicontract.STATUS_CONTRACT, uicontract.STATE_CONTRACT, uicontract.PROBE_CONTRACT):
        for key, row in table.items():
            if row.get("renderer"):
                assert row["renderer"] in fns, "%s: 렌더러 %s 없음" % (key, row["renderer"])
            if row.get("element"):
                assert ('id="%s"' % row["element"]) in html, "%s: element #%s 없음" % (key, row["element"])


@gui
def test_refresh_calls_contract_renderers():
    """index.html 의 refresh() 본문 안에서 STATUS/STATE 계약의 렌더러가 실제로 불리는가 — 「글자가 근처에 있는가」가 아니라 함수 본문(중괄호 짝)으로 자른다."""
    import uicontract
    html = (APP / "ui" / "index.html").read_text(encoding="utf-8")
    i = html.find("async function refresh()")
    assert i > 0, "refresh() 없음"
    depth, j = 0, html.find("{", i)
    for k in range(j, len(html)):
        depth += html[k] == "{"; depth -= html[k] == "}"
        if depth == 0:
            break
    body = html[j:k]
    for table in (uicontract.STATUS_CONTRACT, uicontract.STATE_CONTRACT):
        for key, row in table.items():
            r = row.get("renderer")
            if r and r != "refresh":
                assert (r + "(") in body or (r + "(") in html[html.find("async function refresh()"):], "refresh() 가 %s 를 부르지 않음 (%s)" % (r, key)


def test_status_keys_all_in_contract(tmp_path, monkeypatch):
    import store, engine, uicontract
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    st = engine.status()
    extra = set(st.keys()) - set(uicontract.STATUS_CONTRACT.keys()) - {"ok", "instance"}
    assert not extra, "계약에 없는 status 키: %s" % extra


# ───────────────────────────── 3. 가드 (▼ 도메인 — 최소 6종을 채운다)
def test_guard_pseudonymize_roundtrip():
    import guard
    txt, mapping = guard.pseudonymize("김민수(010-1234-5678)가 참여했다", ["김민수"])
    assert "김민수" not in txt and "010-1234-5678" not in txt
    assert guard.restore(txt, mapping) .startswith("김민수")


def test_guard_scan_leak_catches_rrn():
    import guard
    assert guard.scan_leak("주민번호 900101-1234567")


#  ★ 더미 치환 주의 — {{도메인 금지 문구 N}} 과 guard.py 안의 실제 금지 문구를 **같은 더미값**(예:
#  전부 "dummy")으로 치환하면 이 아래 2건(parametrize 2 케이스)이 실패하는 게 정상이다(금지문구=치환문구
#  가 되어 guard.filter_output 로직과 시험 기대값이 동시에 무너짐). 코드 결함이 아니다 — 도메인 값을
#  채워 금지문구≠치환문구로 만들면(예: "{{도메인 금지 문구 1}}" → 실제 금지어, phrase 인자도 그 실제
#  금지어) 통과한다. docs/40 §3 참조.
@pytest.mark.parametrize("phrase", ["{{도메인 금지 문구 1}}", "{{도메인 금지 문구 2}}"])
def test_output_filter_blocks_forbidden_claims(phrase):
    import guard
    out, removed = guard.filter_output("서론. " + phrase + " 결론.")
    assert phrase not in out and removed


def _irreversible_actions():
    try:
        import engine
    except ImportError:          # 뼈대 단계(app/ 없음) 수집용 — 실제 앱에서는 항상 import 된다
        return []
    return sorted(a for a, m in engine._ACTIONS.items() if m.get("irreversible"))


@pytest.mark.parametrize("act", _irreversible_actions() or ["__해당없음__"])
def test_irreversible_action_needs_confirm(act, monkeypatch):
    """★V4.12 항진 시험 교체 — 구판은 `meta["irreversible"] is True` 를 방금 표에서 읽은 값에 대고 확인해 절대 실패하지 않았다.
    이 판은 실제로 chat() 을 불러(LLM 은 fake) 비가역 액션이 confirm 없이는 job 을 시작하지 않고 needs_confirm 을 돌려주는지 본다."""
    if act == "__해당없음__":
        pytest.skip("해당없음 — 비가역 액션 없음(plan.md §2 도구 표와 일치해야 한다 — docs/50 §7-4b)")
    import engine, llm
    monkeypatch.setattr(llm, "call_json", lambda *a, **k: {"ok": True, "data": {"action": act, "args": {}, "reply": ""}, "error": None})
    started = []
    out = engine.chat("실행해 줘", False, lambda fn: started.append(fn) or "job")
    assert out.get("needs_confirm") is True, "비가역 액션 %s 가 confirm 없이 통과" % act
    assert not started, "confirm 전에 job 이 시작됐다: %s" % act
    out2 = engine.chat("실행해 줘", True, lambda fn: started.append(fn) or "job")
    assert not out2.get("needs_confirm"), "confirm=True 인데도 다시 확인을 요구한다: %s" % act


def test_reset_path_requires_force_and_backup(tmp_path, monkeypatch):
    import store, engine
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "state_backups")
    store.update_state(lambda s: s.__setitem__("items", {"1": {"status": "done"}}))
    with pytest.raises(engine.Blocked):
        engine.intake(**{"{{필수 필드}}": "x"})
    engine.intake(**{"{{필수 필드}}": "x"}, force=True)
    assert list((tmp_path / "state_backups").glob("state_before_*.json"))


def test_phase_change_creates_snapshot(tmp_path, monkeypatch):
    import store
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "state_backups")
    monkeypatch.setattr(store, "_PHASE_MARK", {"v": None})
    store.update_state(lambda s: s.__setitem__("phase", "a"))
    store.update_state(lambda s: s.__setitem__("phase", "b"))
    assert list((tmp_path / "state_backups").glob("state_phase_a_*.json")), "단계가 바뀌었는데 스냅샷이 없다"


# ───────────────────────────── 3b. 「정의됨 ≠ 호출됨」 — 설계 문서가 «구현했다»고 적은 함수가 실제로 있고, 다른 곳에서 불리는가
def _doc_funcs():
    """bom.md·기획안_구현_대조표.md 에 `module.func` 꼴로 적힌 것 전부."""
    out = set()
    for name in ("bom.md", "기획안_구현_대조표.md"):
        p = ROOT / "_개발자료" / "_design" / name
        if p.exists():
            out |= set(re.findall(r"`([a-z_][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)(?:\(\)?)?`", p.read_text(encoding="utf-8")))
    return {(m, f) for m, f in out if (APP / (m + ".py")).exists()}


@pytest.mark.parametrize("mod,fn", sorted(_doc_funcs()) or [("engine", "status")])
def test_documented_function_exists_and_is_called(mod, fn):
    src = (APP / (mod + ".py")).read_text(encoding="utf-8")
    assert re.search(r"^\s*def\s+%s\s*\(" % re.escape(fn), src, re.M), "%s.%s 정의 없음(문서만 있음)" % (mod, fn)
    callers = 0
    for p in list(APP.glob("*.py")) + list((APP / "ui").glob("*.html")):
        body = p.read_text(encoding="utf-8", errors="ignore")
        pat = r"(?<![\w.])%s\.%s\s*\(" % (mod, fn) if p.name != mod + ".py" else r"(?<![\w.])%s\s*\(" % fn
        n = len(re.findall(pat, body)) - (1 if p.name == mod + ".py" else 0)   # 자기 정의 1개 제외
        callers += max(n, 0)
    assert callers > 0, "%s.%s 는 정의만 있고 호출부가 없다(만들어 놓고 안 쓰는 코드)" % (mod, fn)


def test_second_verifier_is_wired():
    """LLM 3자리 중 「2차 검증(Codex)」이 화면 칩(설치 확인)만이 아니라 실제 파이프라인에서 불리는가."""
    src = (APP / "engine.py").read_text(encoding="utf-8")
    m = re.search(r"providers\s*=\s*\[\s*[\"']codex[\"']", src)
    assert m, "engine.py 어디에도 providers=['codex', …] 호출이 없다 — 2차 검증이 배선되지 않음"
    # 그 호출을 담은 함수가 다시 어딘가에서 불리는가
    head = src[:m.start()]
    fn = re.findall(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", head, re.M)[-1]
    assert len(re.findall(r"(?<![\w.])%s\s*\(" % fn, src)) >= 2, "%s 는 정의만 있고 호출되지 않음" % fn


# ───────────────────────────── 3b+. 요구 값 강제 대조 (★V4.11 신설, docs/50 §7-4b)
# `_개발자료/_qc/요구값_강제_대조표.md`(templates/양식/요구값_강제_대조표.md 양식)에 적힌 증명 시험
# 이름은 이 파일에 실제로 있어야 한다. 아래 4개는 그 최소 뼈대 — ▼ 도메인 구현에 맞게 채운다.
# 가드 위반 시험은 가드 유형(결정형/판단형)별로 갈라서 쓴다(docs/50 §7-4b 와 일치):
# 결정형은 무조건 차단 시험 1개, 판단형은 "승인 화면 표시 + 승인 없이 비가역 행동 불가" 시험 1개.
# pytest.skip 은 "collect 는 되지만 아직 도메인 값을 안 채웠다"는 뜻이다. 채운 뒤에는 skip 을 지운다.
# ★V4.12 아래 skip 뼈대가 출하본에 남으면 test_no_skeleton_skips_left 가 실패한다(docs/40 §3 — grep 1차 필터, 한계 있음).

def test_call_budget_counts_actual_calls_incl_retry_fallback():
    """호출·비용 한도는 «사용자 요청 1건당 실제 LLM 호출 수(재시도·폴백 포함)»로 세야 한다(docs/50 §7-4b).
    "요청 1건 = 카운트 1"로만 세면 provider 별 내부 재시도·폴백 전환은 안 세게 되어, 실제 호출은
    표시 한도의 몇 배가 될 수 있다(실사고: 호출 헬퍼가 provider 마다 재시도 N회 + 폴백 provider 로
    다시 N회를 도는데 예산 차감은 "호출 1회 요청" 단위로만 셈). ▼ 도메인: 재시도·폴백이 실제로 도는
    상황을 monkeypatch 로 재현하고, 예산 차감이 그 실제 시도 횟수를 반영하는지 확인한다."""
    pytest.skip("도메인 구현에 맞게 채워야 하는 뼈대 — docs/50 §7-4b · 요구값_강제_대조표.md 참조")


def test_termination_condition_matches_declared():
    """종료 조건은 선언한 조건 그대로 구현돼야 한다 — 대체 조건으로 바꿔치기 금지(docs/50 §7-4b).
    예: "N회 연속 오류 시 종료"라 선언했으면, 실패가 남아 있는데 다른 조건(예: 시간 경과)만으로
    조용히 다음 단계(승인 등)로 진행하면 안 된다. ▼ 도메인: 선언한 종료 조건과 실제 루프 탈출
    조건이 같은 변수·같은 의미를 재는지 확인한다."""
    pytest.skip("도메인 구현에 맞게 채워야 하는 뼈대 — docs/50 §7-4b · 요구값_강제_대조표.md 참조")


def test_decision_type_guard_blocks_progress_unconditionally():
    """가드 유형이 «결정형»(숫자·한도·종료 조건·주소록 대조·참석자 대조 등 코드로 확정 판정 가능한 값)인
    위반은 다음 단계(승인 포함)로 예외 없이 진행을 막아야 한다(fail-closed, docs/50 §7-4b — 판단형 예외는
    적용되지 않는다). 상한 도달 후에도 통과시키거나, 결정형 판정이 실패했는데 그대로 승인 단계로 넘어가면
    Critical. ▼ 도메인: 결정형 위반 상태를 인위로 만들고, 다음 단계 진입 함수가 실제로 막히는지(예외·
    상태값 변화 없음)를 확인한다."""
    pytest.skip("도메인 구현에 맞게 채워야 하는 뼈대 — docs/50 §7-4b · 요구값_강제_대조표.md 참조")


def test_judgment_type_guard_shows_unresolved_and_blocks_irreversible_without_approval():
    """가드 유형이 «판단형»(코드로 확정 못 하는 날조·창작 등)인 위반은 사람 승인 게이트로 넘기는 것이
    정상 경로다(docs/50 §7-4b 판단형 가드 예외) — 이 시험은 "진행 자체를 막는지"가 아니라 다음 둘을
    확인한다: (a) 미해결 항목이 승인 화면에 구체적으로 표시되는가 (b) 승인 없이는 비가역 행동(발송·게시·
    결제·삭제)이 실행되지 않는가. 둘 중 하나라도 안 되면 Critical. ▼ 도메인: 판단형 위반 상태를 인위로
    만들고, 승인 화면 데이터에 그 미해결 항목이 나타나는지 + 승인 없이 비가역 함수를 불러도 실행이 막히는지
    확인한다."""
    pytest.skip("도메인 구현에 맞게 채워야 하는 뼈대 — docs/50 §7-4b · 요구값_강제_대조표.md 참조")


# ───────────────────────────── 3b++. 차분 결속 시험 (★V4.12 — 규격 단일 출처 docs/40 §1b, 판정 docs/50 §7-4b-2)
# 승인 뒤 «결과를 바꿀 수 있는 입력»을 하나씩 바꿨을 때, 달라진 payload 가 그 승인으로 transport 에 닿으면 실패.
# 비가역 도구(게시·삭제·결제·전송)가 하나라도 있으면 IRREVERSIBLE = True 로 바꾸고 ▼ 도메인 함수를 채운다.
# 채우지 않으면 NotImplementedError 로 빨갛게 남는다(skip 으로 숨지 않는다). fake 전용 — 실키·실호출·실발송 없음(docs/50 7-2).
IRREVERSIBLE = False   # ▼ 도메인: plan.md §2 도구 표·Phase 1 coverage 선행 행(비가역 도구 유무)·docs/05 10번째 기록과 같아야 한다(V1 이 대조)
EXEMPT = {             # 비교에서 빼는 입력 {키: 사유}. 사유가 비면 시험 실패. 키 표기: env:/profile:/draft: (docs/40 §1b). ▼ 도메인 것을 더한다
    # 뼈대 자체(ui_skeleton·setup_helper)가 읽는 환경변수 — 전송 payload 와 무관(그 사실이 달라지면 이 사유를 다시 검토)
    "env:LOCALAPPDATA": "토큰·런타임 파일 위치(Windows 사용자 폴더) — 전송 내용·대상에 안 들어감",
    "env:NO_BROWSER": "화면 서버 시작 때 브라우저 자동 열기 여부 — 전송과 무관",
    "env:UI_ALLOW_MULTI": "화면 서버 다중 기동 허용 여부 — 전송과 무관",
}
TABLE_FIELDS = set()   # ▼ 도메인(보충용): 요구값_강제_대조표 11행·docs/05 10번째에 적은 결속 필드 이름. 정답은 아래 기계 추출이고 이 표는 대조용이다
_ENV_RE = [re.compile(p) for p in (r"os\.environ\.get\(\s*[\"']([A-Za-z_]\w*)", r"os\.environ\[\s*[\"']([A-Za-z_]\w*)", r"os\.getenv\(\s*[\"']([A-Za-z_]\w*)")]


def _extract_inputs() -> set:
    """결과를 바꿀 수 있는 입력을 **코드에서** 뽑는다(작성자 표에서 가져오면 «표가 좁으면 시험도 좁은» 자기참조가 된다).
    (a) 프로필·설정 키 전체  (b) .env·환경변수 키 전수(os.environ·os.getenv)  (c) 초안 필드 전체. ▼ 도메인: 상수 이름이 다르면 아래 튜플에 더한다."""
    found = set()
    for p in APP.glob("*.py"):
        src = p.read_text(encoding="utf-8", errors="ignore")
        for rx in _ENV_RE:
            found |= {"env:" + k for k in rx.findall(src)}
    try:
        import engine
    except ImportError:
        return found
    for name in ("PROFILE_FIELDS", "SETTINGS_FIELDS"):
        found |= {"profile:" + str(k) for k in getattr(engine, name, ())}
    for name in ("DRAFT_FIELDS",):
        found |= {"draft:" + str(k) for k in getattr(engine, name, ())}
    return found


class FakeTransport:
    """마지막 소켓(HTTP·SMTP 호출)만 가짜로 바꾼다. 호출 전체 인자(URL·헤더·body)를 기록하고 Idempotency-Key 만 비교에서 뺀다."""
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers=None, body=None, **kw):
        h = {str(k).lower(): v for k, v in (headers or {}).items() if str(k).lower() != "idempotency-key"}
        self.calls.append({"url": url, "headers": h, "body": body, "extra": kw})
        return {"ok": True}


def _run_flow(monkeypatch, tmp_path, mutate=None, when="after_approval", approval_disabled=False) -> list:
    """▼ 도메인 — 실제 «승인 → 발송» 경로를 fake LLM·FakeTransport 로 실행하고 transport 가 받은 호출 목록을 돌려준다.
    · 항목 2건 이상을 발송하는 흐름이어야 한다(두 번째 건 시점 주입용).
    · mutate=(입력 이름, "other_valid"|"empty") — when 시점에 그 입력을 바꾼다: "after_approval"(승인 직후·발송 전) / "second_item_before_transport"(2번째 건 transport 직전).
    · approval_disabled=True — 승인 유효 판정을 항상 통과로 바꾼 대조군.
    · 임시 폴더·monkeypatch 로만 쓴다(실 state 금지). 실키·실호출 금지."""
    raise NotImplementedError("▼ 도메인: docs/40 §1b 규격대로 채운다")


def test_irreversible_flag_matches_tools():
    """IRREVERSIBLE=False 로 남아 차분 결속 시험이 통째로 skip 되는 것을 막는 자동 보조 검사(docs/50 §7-4b-2). 판정은 **코드 신호만** —
    engine._ACTIONS 에 irreversible 액션이 있는데 IRREVERSIBLE=False 면 실패. plan.md 는 읽지 않는다(표 형식·표기가 제각각이라 파싱하면 오탐).
    plan.md 도구 표의 비가역 도구 유무 ↔ IRREVERSIBLE 일치는 V1 이 `templates/V1_지시서.md` 「IRREVERSIBLE 스위치 일치」 줄로 사람이 판정한다."""
    if IRREVERSIBLE:
        return
    acts = _irreversible_actions()
    assert not acts, "engine._ACTIONS 에 비가역 액션 %s 이 있는데 IRREVERSIBLE=False — 차분 결속 시험이 skip 된다" % acts[:3]


def test_binding_inputs_are_extracted_from_code():
    if not IRREVERSIBLE:
        pytest.skip("해당없음 — 비가역 도구 없음(IRREVERSIBLE=False)")
    inputs = _extract_inputs()
    assert inputs, "코드에서 추출된 입력이 0개 — _extract_inputs 가 이 앱 구조를 못 읽는다(상수 이름을 더한다)"
    bad = [k for k, why in EXEMPT.items() if not str(why).strip()]
    assert not bad, "EXEMPT 사유가 비어 있다: %s" % bad
    code_only = inputs - {"%s" % t for t in TABLE_FIELDS} - set(EXEMPT)
    assert not code_only, "코드엔 있는데 표(TABLE_FIELDS)에도 EXEMPT 에도 없다 — 표가 좁다: %s" % sorted(code_only)
    table_only = set(TABLE_FIELDS) - inputs
    assert not table_only, "표엔 있는데 코드에서 못 찾았다(추출 규칙이 좁거나 표가 틀림): %s" % sorted(table_only)


@pytest.mark.parametrize("when", ["after_approval", "second_item_before_transport"])
@pytest.mark.parametrize("variant", ["other_valid", "empty"])
def test_binding_differential(when, variant, tmp_path, monkeypatch):
    if not IRREVERSIBLE:
        pytest.skip("해당없음 — 비가역 도구 없음(IRREVERSIBLE=False)")
    base = _run_flow(monkeypatch, tmp_path, mutate=None, when=when)
    assert base, "기준 실행에서 transport 호출이 0건 — 시험이 아무것도 못 잰다"
    leaked = []
    for key in sorted(_extract_inputs() - set(EXEMPT)):
        sent = _run_flow(monkeypatch, tmp_path, mutate=(key, variant), when=when)
        for i, call in enumerate(sent):
            if i >= len(base) or call != base[i]:
                leaked.append("%s(%s,%s) → %d번째 호출이 승인 시점과 다른데 전송됨" % (key, variant, when, i + 1))
    assert not leaked, "승인 뒤 바뀐 payload 가 그 승인으로 나갔다:\n" + "\n".join(leaked)


def test_binding_differential_control_changes_payload(tmp_path, monkeypatch):
    """대조군 — 승인 검사를 무력화했을 때 payload 가 실제로 달라지는 입력이 1개 이상 있어야 시험이 «죽어 있지 않다»."""
    if not IRREVERSIBLE:
        pytest.skip("해당없음 — 비가역 도구 없음(IRREVERSIBLE=False)")
    base = _run_flow(monkeypatch, tmp_path, mutate=None, approval_disabled=True)
    moved = [k for k in sorted(_extract_inputs() - set(EXEMPT))
             if _run_flow(monkeypatch, tmp_path, mutate=(k, "other_valid"), approval_disabled=True) != base]
    assert moved, "승인을 꺼도 어떤 입력도 payload 를 바꾸지 못한다 — 입력 주입 또는 payload 덤프가 죽어 있다"


# ───────────────────────────── 3c. 규모 하한
def test_scale_minimum():
    """plan.md 규모(S/M/L)에 맞는 시험 수 — _개발자료/tests/*.py 의 test_ 함수 수(parametrize 는 1로 센다)."""
    n = 0
    for p in Path(__file__).parent.glob("test_*.py"):
        n += len(re.findall(r"^def test_\w+\(", p.read_text(encoding="utf-8"), re.M))
    assert n >= MIN_TESTS[SCALE], "시험 %d건 < 규모 %s 하한 %d" % (n, SCALE, MIN_TESTS[SCALE])


# ───────────────────────────── 4. 시험 파일 위생
def test_app_files_exist():
    # ★V4.12 개명(구 test_mutation_sanity) — 이름과 달리 돌연변이를 하지 않고, 시험이 실제 앱 파일을 읽는 경로가 맞는지만 본다
    assert (APP / "run.py").exists() and (TRACK != "gui" or (ROOT / "시작.bat").exists())


_SKELETON_MARK = "도메인 구현에 맞게 채워야 하는 뼈대"


def test_no_skeleton_skips_left():
    """★V4.12 skip·항진 잔존 1차 필터 — 뼈대 상태의 `pytest.skip("…도메인 구현에 맞게 채워야 하는 뼈대…")`·`assert True` 가 시험 파일에 남아 있으면 실패.
    ⚠ 한계(docs/40 §3): 이 시험은 문자열 필터일 뿐이다 — skipif·xfail 조합, `h == h` 변형, payload 를 안 읽는 시험은 못 잡는다.
    실효 검증은 차분 결속 시험(3b++)이 실제로 도는가 + V1 의 시험 코드 읽기다."""
    rx = re.compile(r"^\s*(?:pytest\.skip\(.*" + re.escape(_SKELETON_MARK) + r"|assert\s+True\b)", re.M)
    left = []
    for p in Path(__file__).parent.glob("test_*.py"):
        for m in rx.finditer(p.read_text(encoding="utf-8")):
            left.append("%s: %s" % (p.name, m.group(0).strip()[:60]))
    assert not left, "skip·항진 뼈대가 남아 있다 — 채우거나(해당없음이면 사유를 적어 지운다): %s" % left


# ================================================================ 값 일치 대조 (V4.5 신설)
# 왜 있나: 변주 제조에서 반려의 대부분이 「코드는 맞는데 문서 하나가 옛 값」이다.
#   같은 사실(이름·포트·폴백 순서 등)이 plan·bom·SVG·헌법·README·매뉴얼·코드 등 10곳 넘게 흩어져 있어,
#   하나를 바꾸면 사람이든 AI든 반드시 한두 곳을 빠뜨린다. 「조심하자」로는 못 막는다.
#   기존 test_documented_function_exists_and_is_called 는 **함수**만 대조하고 **값**은 안 봤다.
# 실측(2026-09-18 thesis-agent 변주): 이 시험이 없어서 재단 11곳 계획이 실제 15곳이 됐고,
#   설계 V1 1회·출하 V1 1회가 전부 「문서 불일치」로 반려됐다. 왕복 때문에 60분 시간표를 넘겼다.
# 이 시험이 있으면 그 반려가 **Phase 6b 시험 단계에서 즉시** 잡혀 검증 왕복이 사라진다.

def _doc(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_value_brand_name_matches_everywhere():
    """이름 — ui.py 의 BRAND 가 단일 출처. 화면·문서가 같은 이름을 써야 한다.
    ⚠️ 「BRAND 한 줄만 바꾸면 다 반영된다」는 말은 **사실이 아니다** — index.html 은 문자열을 박아 둔다."""
    ui_p = APP / "ui.py"
    if not ui_p.exists():
        pytest.skip("GUI 트랙 아님")
    m = re.search(r'^BRAND\s*=\s*"([^"]+)"', ui_p.read_text(encoding="utf-8"), re.M)
    if not m:
        pytest.skip("BRAND 상수 없음")
    brand = m.group(1)
    html_p = APP / "ui" / "index.html"
    if html_p.exists():
        html = html_p.read_text(encoding="utf-8")
        titles = re.findall(r"<title>([^<]*)</title>", html) + re.findall(r"<h1>([^<]*)</h1>", html)
        for t in titles:
            if "{{" in t or not t.strip():
                continue
            assert brand in t, "index.html 의 「%s」 가 BRAND(%s)를 안 쓴다 — 화면에 옛 이름이 뜬다" % (t[:40], brand)


def test_value_port_matches_everywhere():
    """포트 — ui.py 가 단일 출처. 매뉴얼·README 주소가 다르면 사용자가 눌러도 안 열린다."""
    ui_p = APP / "ui.py"
    if not ui_p.exists():
        pytest.skip("GUI 트랙 아님")
    m = re.search(r"^PORT\s*=\s*(\d+)", ui_p.read_text(encoding="utf-8"), re.M)
    if not m:
        pytest.skip("PORT 상수 없음")
    port = m.group(1)
    for rel in ("README.md", "사용자 매뉴얼(설치 및 사용법).html"):
        for found in set(re.findall(r"localhost:(\d{4})", _doc(rel))):
            assert found == port, "%s 가 localhost:%s 를 가리킨다 — 실제 포트는 %s" % (rel, found, port)


def test_value_llm_chain_matches_docs():
    """LLM 폴백 체인 — 코드가 단일 출처. 문서가 옛 체인을 적고 있으면 안 된다.
    실측: 체인에 provider 를 하나 추가했는데 헌법(CLAUDE.md)만 안 고쳐져 출하 V1 Critical 이 됐다."""
    eng_p = APP / "engine.py"
    if not eng_p.exists():
        pytest.skip("engine.py 없음")
    chains = re.findall(r"providers=\[([^\]]+)\]", eng_p.read_text(encoding="utf-8"))
    if not chains:
        pytest.skip("providers 지정 없음")
    provs = {x.strip().strip('"\'') for c in chains for x in c.split(",") if x.strip()}
    for rel in ("CLAUDE.md", "_개발자료/_design/plan.md", "_개발자료/_design/bom.md"):
        t = _doc(rel)
        if not t:
            continue
        for prov in provs:
            assert prov in t, "%s 에 LLM provider 「%s」 가 없다 — 코드가 쓰는 체인 %s 와 어긋난다" % (rel, prov, sorted(provs))


def test_value_repeated_counts_match_across_docs():
    """「N종」·「N개」처럼 문서마다 반복되는 개수가 서로 달라지지 않게 한다.
    실측: 가드 개수를 8종으로 늘렸는데 plan.md 만 7종으로 남아 설계 V1 에서 반려됐다."""
    docs = ["_개발자료/_design/plan.md"] + [
        str(p.relative_to(ROOT)) for p in (ROOT / "_개발자료" / "_design").glob("*.svg")
    ] if (ROOT / "_개발자료" / "_design").exists() else []
    found = {}
    for rel in docs:
        for label, n in re.findall(r"(가드|구성요소|자리)\s*(\d+)\s*종", _doc(rel)):
            found.setdefault(label, {}).setdefault(n, []).append(rel)
    for label, byval in found.items():
        assert len(byval) <= 1, "「%s N종」 표기가 문서마다 다르다: %s" % (label, {k: v for k, v in byval.items()})
