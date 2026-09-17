# -*- coding: utf-8 -*-
"""시험 뼈대 — 에신 V4 templates/test_gates.py → _개발자료/tests/test_gates.py

최소 묶음(docs/40 시험 규격). 규모별 하한: S 20 · M 60 · L 150 건. 이 파일은 그 뼈대 — 도메인 가드를 채운다.
실행: set PYTHONUTF8=1 && python -m pytest _개발자료/tests -q -p no:cacheprovider
원칙: ① 상태를 쓰는 함수는 임시 state 로만 ② «글자가 근처에 있는가» 시험 금지(함수 본문·라우트 경계로 자른다)
      ③ 새 시험은 일부러 망가뜨려 빨간불이 나는지 본 뒤 넣는다(돌연변이 1회) ④ 미확인 ≠ 통과
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


@pytest.mark.parametrize("phrase", ["{{도메인 금지 문구 1}}", "{{도메인 금지 문구 2}}"])
def test_output_filter_blocks_forbidden_claims(phrase):
    import guard
    out, removed = guard.filter_output("서론. " + phrase + " 결론.")
    assert phrase not in out and removed


def test_irreversible_action_needs_confirm():
    import engine
    for act, meta in engine._ACTIONS.items():
        if meta.get("irreversible"):
            assert meta["irreversible"] is True   # 액션봇 confirm 관문이 표에 박혀 있다


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


# ───────────────────────────── 3c. 규모 하한
def test_scale_minimum():
    """plan.md 규모(S/M/L)에 맞는 시험 수 — _개발자료/tests/*.py 의 test_ 함수 수(parametrize 는 1로 센다)."""
    n = 0
    for p in Path(__file__).parent.glob("test_*.py"):
        n += len(re.findall(r"^def test_\w+\(", p.read_text(encoding="utf-8"), re.M))
    assert n >= MIN_TESTS[SCALE], "시험 %d건 < 규모 %s 하한 %d" % (n, SCALE, MIN_TESTS[SCALE])


# ───────────────────────────── 4. 돌연변이 자가 검사 (이 파일이 진짜 재는지)
def test_mutation_sanity():
    # 시험이 «항상 통과»하는 헛시험이 아닌지 — 실제 파일을 읽는다는 것을 한 번 확인
    assert (APP / "run.py").exists() and (TRACK != "gui" or (ROOT / "시작.bat").exists())
