# -*- coding: utf-8 -*-
"""guard.py 뼈대 (에신 V4 templates/guard_skeleton.py → app/guard.py) — 가명화(성명·주민번호·연락처·이메일·주소)·복원·누출 스캔·출력 필터·페르소나 검사·AI 고지.
원본 설명: — 안전 체계(코드 강제). 프롬프트 부탁이 아니라 실행 전후 검사·차단.

부품 출처: 공증 rules.py `pseudonymize`·`restore` + 정규식 4종(BOM 🟡 — 여권 제거, 이메일 추가).
자체 제작(🏭): 출력 필터(법적·제도적 판정 자기 단정 금지), 페르소나 이탈 검사, AI 활용 고지문, 전송 직전 2차 스캔.

헌법 제약(리서치 2026-09-17):
- ② 법적·제도적 최종 판정 문구 생성 금지 → `filter_output()`이 문장을 치환하고 고지문을 붙인다.
- ④ AI 활용 고지 기본 포함 → `ai_disclosure()` (settings.ai_disclosure=False로만 해제).
"""
from __future__ import annotations
import re, string

# ---------------------------------------------------------------- 가명화 (공증 🟡)
_RRN_RE = re.compile(r"(?<!\d)\d{6}-?\d{7}(?!\d)")
_PHONE_RE = re.compile(
    r"(?<!\d)01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)"
    r"|(?<!\d)0\d{1,2}[-.)]\s?\d{3,4}[-.\s]\d{4}(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ADDR_RE = re.compile(
    r"[가-힣A-Za-z0-9]+(?:로|길)\s*\d+(?:-\d+)?(?:\s*,?\s*\d+동)?(?:\s*,?\s*\d+호)?"
    r"|\d+(?:-\d+)?번지(?:\s*\d+호)?"
    r"|(?:[가-힣]+(?:아파트|빌라|오피스텔)\s*)?\d+동\s*\d+호")
_PATTERNS = (("주민번호", _RRN_RE), ("연락처", _PHONE_RE), ("이메일", _EMAIL_RE), ("주소", _ADDR_RE))


def pseudonymize(text: str, names: list[str] | None = None) -> tuple[str, dict]:
    """개인 식별자 토큰 치환. (masked, mapping{token: 원문}). mapping은 메모리에서만 — 파일 기록 금지."""
    mapping: dict = {}
    counters = {k: 0 for k, _ in _PATTERNS}
    masked = str(text)

    def _sub(pattern, category, s):
        def _repl(m):
            orig = m.group(0)
            for tok, o in mapping.items():
                if o == orig and tok.startswith("[%s#" % category):
                    return tok
            counters[category] += 1
            tok = "[%s#%d]" % (category, counters[category])
            mapping[tok] = orig
            return tok
        return pattern.sub(_repl, s)

    for cat, pat in _PATTERNS:
        masked = _sub(pat, cat, masked)

    labeled = []
    for i, nm in enumerate(names or []):
        nm = str(nm).strip()
        if len(nm) < 2:
            continue
        label = string.ascii_uppercase[i] if i < 26 else str(i + 1)
        labeled.append((nm, "[참여자%s]" % label))
    for nm, tok in sorted(labeled, key=lambda x: -len(x[0])):   # 긴 이름부터(부분 겹침 방지)
        if nm in masked:
            masked = masked.replace(nm, tok)
            mapping[tok] = nm
    for nm, tok in labeled:                                        # 로마자 이름은 성·이름 따로도
        if " " in nm:
            for part in nm.split():
                part = part.strip(".,")
                if len(part) >= 3:
                    masked = re.sub(r"(?<![0-9A-Za-z])" + re.escape(part) + r"(?![0-9A-Za-z])", tok, masked)
    return masked, mapping


def restore(text: str, mapping: dict) -> str:
    out = text
    for tok, orig in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(tok, orig)
        bare = tok.strip("[]")
        out = re.sub(r"(?<![가-힣A-Za-z0-9])" + re.escape(bare) + r"(?![가-힣A-Za-z0-9#])", orig, out)
    return out


def scan_leak(text: str) -> list[str]:
    """전송 직전 2차 스캔 — 히트가 있으면 호출을 막는다(fail-closed). 반환: 발견 카테고리 목록."""
    hits = []
    for cat, pat in _PATTERNS:
        if cat == "주소":
            continue   # 주소 패턴은 오탐이 잦아 2차 스캔에서는 제외(1차에서 이미 치환)
        if pat.search(text):
            hits.append(cat)
    return hits


# ---------------------------------------------------------------- 출력 필터 (헌법 ②)
_VERDICT_PATTERNS = [
    # ▼ 도메인: 코드가 절대 내보내면 안 되는 «최종 판정» 문장 패턴 (예: "본 문서는 법적 효력이 있다", "표절이 없다", "승인되었다")
    (re.compile(r"{{금지 문장 정규식 1}}"), "{{치환 문구 1}}"),
]
NOTICE = "※ {{제도적·법적 최종 판정}}은 이 도구가 하지 않습니다 — 사람이 확인해야 합니다."


def filter_output(text: str) -> tuple[str, list[str]]:
    """자기 단정 문구를 고지문으로 치환. 반환 (text, 치환된 원문 목록)."""
    removed = []
    out = text
    for pat, repl in _VERDICT_PATTERNS:
        for m in pat.finditer(out):
            removed.append(m.group(0))
        out = pat.sub(repl, out)
    return out, removed


# ---------------------------------------------------------------- 페르소나 이탈 검사
_FIRST_PERSON = re.compile(r"(?<![가-힣])(저는|제가|나는|내가|우리는|필자는)\s")
_ABSOLUTE = re.compile(r"(명백히|확실히|절대(로)?|분명히|의심의 여지 없이|틀림없이)")
_REVIEWER_TONE = re.compile(r"(심사\s*의견|보완\s*요망|재검토\s*바람|수정\s*요청|평가하자면|점수를 매기면)")


def persona_check(text: str) -> list[dict]:
    """규칙 위반 위치 목록. 3회 재생성 후에도 남으면 미달 보고."""
    issues = []
    for name, pat in (("1인칭", _FIRST_PERSON), ("단정 부사", _ABSOLUTE), ("심사 어조", _REVIEWER_TONE)):
        for m in pat.finditer(text):
            s = max(0, m.start() - 20); e = min(len(text), m.end() + 20)
            issues.append({"rule": name, "where": text[s:e].replace("\n", " ")})
    return issues


# ---------------------------------------------------------------- AI 활용 고지 (헌법 ④)
DEFAULT_DISCLOSURE = (
    "{{산출물에 붙일 AI 활용 고지 기본문 — 사용자 기준이 있으면 그것으로 대체}}"
)


def ai_disclosure(profile: dict, settings: dict) -> str | None:
    """settings.ai_disclosure가 명시적으로 False가 아니면 항상 문구 반환(학교 프로필 문구 우선)."""
    if settings.get("ai_disclosure") is False:
        return None
    return (profile or {}).get("ai_disclosure_text") or DEFAULT_DISCLOSURE
