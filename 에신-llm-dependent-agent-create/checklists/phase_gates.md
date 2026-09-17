# Phase 게이트 — "이 파일이 있어야 다음 Phase" (checklists/phase_gates.md · 에신 V4)

> 작성자가 Phase 를 넘길 때 스스로 확인한다. 파일이 없으면 다음 Phase 로 못 간다. 검증자를 부르는 것은 Phase 7 뿐.

| Phase | 있어야 하는 것 | 확인 방법 |
|:-:|---|---|
| 0 → 1 | mbo-천상 연결 확인(파일 존재 + MBO_SPEC_VERSION 마커) · 역할 선언 1줄(대화) · 경계 트리 답(Claude Code 안에서만 → /skill-create) · 작업 폴더 경로 | `ls ~/.claude/skills/mbo-천상/SKILL.md` 또는 `mbo/` |
| 1 → 2 | `_개발자료/_design/plan.md`(templates/양식/plan.md 양식 §1~§5 전부 채움 — docs/10 「발굴 항목 12개」가 §1 좌표·§2 7요소·§3 메타에 빠짐없이 반영) · `{이름}_architecture.svg` 초안(관계도+흐름도) · 분기 3개 답(원자재 A/B · 트랙 · 규모) | plan.md §1 좌표 빈칸 0 |
| 2 → 2.5/3 | `{날짜}_mbo-천상_{이름}.md` + PO "승인" 문구 | 파일 존재 + 승인 일시 |
| 2.5 → 3 (경로 B만) | `_개발자료/_design/phase_2.5_research_{날짜}.md` + PO 게이트 통과 | |
| 3 → 4 | 발굴 카탈로그 또는 원자재 입고 카드 · 라이선스 판정 | |
| 4 → 5 | `_개발자료/_design/bom.md`(5분류, 🔴 분리) · `SOURCE_REUSE_LOG.md` · `THIRD_PARTY_NOTICES.md` | 🔴 항목이 🟢에 없음 |
| 5 → 6 | `_개발자료/_design/phase5_selfcheck.md`(5A 셀프 채점, 80 미만이면 PO 보고) | |
| 6 → 6b | 폴더 표준 전부 존재(app/ · _개발자료/ · 루트 문서 5) · `app/skills/*.md` · `app/uicontract.py` · `_개발자료/tests/` 시험 하한(S 20 / M 60 / L 150) 통과 · GUI 트랙이면 `app/ui/index.html` 이 뼈대 복사본 + `_개발자료/_qc/smoke_ui.py` SMOKE PASS(고정표 자기 대조) · `시작.bat` 실기동 OK · **설계도(SVG·plan) 구현 기준으로 갱신** · `기획안_구현_대조표.md` | `pytest -q` · `시작.bat` |
| 6b → 7 | 시운전 1회 기록(약식·샘플 모드) — 사용자 여정 완주 증거(산출물 파일·state) | 재실행은 여정이 끊겼을 때만 |
| 7 → 8 | `_개발자료/_qc/pre_verify_snapshot/` · `v1_report.md`(PASS 또는 결함 전부 소거) · L 이면 `v2_report.md` · GUI 이면 `v1_gui_대조표.md`(X 0) | 7-5 합격선 |
| 8 → 9 | `출하_정리.py --지움` 실행 · `_개발자료/_qc/출하_보고서.md` · 자산 등재 1줄(`~/.claude/assets/자산-등재.md` 또는 `_개발자료/자산_등재.md`) · `/mbo-천상 report` 결과 MBO 파일에 추기 | |
