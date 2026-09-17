# -*- coding: utf-8 -*-
"""uicontract.py 뼈대 — 서버 결과 ↔ 화면의 «단일 계약». 에신 V4 templates/uicontract.py

## 왜 있나
반복된 함정 ③ 「백엔드 원칙이 화면까지 안 이어짐」 — 백엔드가 「미대조 ≠ 통과」로 막아도 화면이 그 값을 안 읽으면 소용없다.
지금까지는 «규율»(새 키를 넣은 사람이 화면도 고칠 것을 기억)로 막았고 실제로 잊었다. 이 표가 그 규율의 코드판이다.

시험 `_개발자료/tests/test_uicontract.py` 가
    ① 서버가 만드는 결과 키 중 이 표에 없는 키가 있으면 실패
    ② 표의 renderer 함수가 index.html 에 없거나 refresh() 에서 불리지 않으면 실패
    ③ 표의 element id 가 index.html 에 없으면 실패
로 못박는다. 새 키를 넣고 화면을 안 고치면 빨간불 — 기억이 아니라 코드가 막는다.

## 손댈 때
`/api/status` 나 `/api/state` 응답에 새 키를 넣었으면 여기에 한 줄을 같이 적는다.
「화면에 안 그린다」가 맞는 결정이면 renderer=None 으로 적고 **왜**를 note 에 쓴다. 조용히 빠뜨리는 것만 막는다.
⚠️ 이 표는 «그리는지»만 본다. «옳게 그리는지»는 각 항목의 시험이 따로 잡는다.
"""

# ▼ 도메인: /api/status 응답 최상위 키 → 렌더러
STATUS_CONTRACT: dict[str, dict] = {
    "phase":    {"renderer": "renderStages", "element": "stage-list", "note": "우측 진행 단계. 단계 idx 매핑은 refresh() 안"},
    "blocked":  {"renderer": "refresh", "element": "safe-unknown", "note": "차단 코드는 안전 체계 배지(#safe-unknown)에 — refresh() 가 직접 채운다"},
    "items":    {"renderer": "refresh", "element": "chapProg", "note": "{{작업 단위}}별 상태·점수·호출 수 — refresh() 가 #chapProg 에 그린다"},
    "history":  {"renderer": None, "element": None, "note": "호출 누계는 화면에 안 그린다 — 로그 폴더에서 본다"},
}

# ▼ 도메인: /api/state 응답 키 → 렌더러 (화면이 읽는 것만 적는다)
STATE_CONTRACT: dict[str, dict] = {
    "intake":    {"renderer": "renderJobList", "element": "gate-list", "note": "{{작업 단위}} 제목·단계"},
    "items":     {"renderer": "renderJobList", "element": "gate-list", "note": "우측 목록 — refresh() 가 items 를 목록으로 바꿔 부른다"},
    "settings":  {"renderer": "refresh", "element": "office-form", "note": "설정 블록 값 채우기"},
    "profile":   {"renderer": "refresh", "element": "standards-form", "note": "사용자 기준 입력칸"},
    # ▼ 도메인 예: "outline": {"renderer": "renderOutline", "element": "outline", "note": "..."}
}

# /api/probe 는 뼈대 JS(verifyRows·chipRow) 가 고정 계약으로 그린다: llm(3자리) · tools[] · kb{} · backup
PROBE_CONTRACT: dict[str, dict] = {
    "llm":    {"renderer": "verifyRows", "element": "llm-status", "note": "세 자리 고정 — 작업/1차 검증/2차 검증"},
    "tools":  {"renderer": "chipRow", "element": "status-list", "note": "found True/False/None 세 값"},
    "kb":     {"renderer": "chipRow", "element": "kb-inject-row", "note": "①~④ + 작업 지식 행 id 로 매핑"},
    "backup": {"renderer": None, "element": "backup-line", "note": "loadStatus 가 직접 textContent 로 채운다"},
}
