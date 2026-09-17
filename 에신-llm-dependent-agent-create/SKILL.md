---
name: 에신
description: "★ 별칭: 에신 (에이전트의 신) ★ LLM 의존형 에이전트 제조 공장 V4 — 요구를 12항목으로 캐내고, mbo-천상으로 목표를 승인받고, 원자재(지정 A / 공개 발굴 B)를 분해·BOM 으로 선별한 뒤, 뼈대 파일(templates/)을 복사해 7대 구성요소(페르소나·목표·LLM·지식베이스·도구·안전 체계·자율 루프)를 조립하고, Phase 7 에서 V1(Claude Teammate Sonnet 5)·V2(Codex, L 규모만) 1회 검증으로 출하한다. 데스크톱형 GUI 는 화면 구성 고정표(좌 페르소나·LLM 3자리·도구·지식베이스 / 우 설정·목록·목표·진행·안전·기록)를 그대로 따른다. mbo-천상 필수(없으면 자동 설치). 사용자가 '에신', '에이전트 만들어', '에이전트 제작', 'llm-dependent-agent-create', '~하는 AI 만들어줘'를 요청할 때 사용. (Claude Code 안에서만 도는 절차는 /skill-create)"
user-invocable: true
version: "4.2"
last_updated: "2026-09-17"
---

<!-- LLM_DEPENDENT_AGENT_CREATE_SPEC_VERSION: V4.2 -->
<!-- V4.2 (2026-09-17) 시범품 V1 검증(79·High 1) 반영 — 「정의됨 ≠ 호출됨」 시험, LLM 3자리 런타임 배선(verify_1st·verify_2nd) 의무, 자기 대조표는 V1 대체 불가 -->
<!-- V4.1 (2026-09-17) 시범 제조(회의록 정리 에이전트) 막힌 곳 7건 반영 — 설치 도우미·설정·기준 라우트/배선(죽은 버튼 0), WORK_MODE SINGLE/MULTI, 가드 두 종류, verify_windows_adapter.ps1 동봉, smoke 진단 보정. 상세 CHANGELOG -->
<!-- V4.0 (2026-09-17) 완전 리모델링 — 2,377행 서술형 본문을 「지휘 문서(이 파일) + docs 모듈 + templates + checklists」 구조로 재편. 변경 이력은 CHANGELOG.md. 스킬 자체의 관계도·흐름도는 _개발자료/_design/에신_V4_architecture.svg — 이 파일의 절 번호와 1:1. -->

# 에신 — LLM 의존형 에이전트 제조 공장 (V4.0)

> **이 파일은 지휘 문서다.** 순서·분기·산출물·게이트만 적는다. 절차의 «어떻게»는 `docs/`, 복사할 파일은 `templates/`, 넘어갈 조건은 `checklists/` 에 있다. 한 Phase 를 할 때는 §3 표에서 그 행을 찾고 거기 적힌 파일만 연다.
> 도식: `_개발자료/_design/에신_V4_architecture.svg` (좌 관계도 · 우 흐름도). 이 파일과 도식이 어긋나면 도식이 틀린 것 — 같이 고친다.

## §0. 이 스킬을 읽는 법 (30초)

```
에신-llm-dependent-agent-create/
├─ SKILL.md            ← 지금 이 파일. §3 Phase 표가 전부다
├─ docs/               읽는 것 — 00 7요소 · 01 GUI 표준구성 · 10 시동·발굴 · 15 리서치 · 20 설계 규격 · 30 조립 공통 · 31 GUI 트랙 · 32 비GUI/웹 · 40 시험 · 50 검증 · 60 출하·운영
├─ templates/          복사해서 채우는 것 — 본체 5(store·llm·guard·engine·run _skeleton.py) · GUI 3(gui_skeleton/index.html · ui_skeleton.py · smoke_ui.py) · 시작.bat · CLAUDE.md · uicontract.py · setup_helper.py · 출하_정리.py · test_gates.py · verify_windows_adapter.ps1 · V1_지시서 · V2_지시서 · 양식/(plan·bom·대조표)
├─ checklists/         넘어갈 조건 — phase_gates · gui_고정표 · v1_v2_대조표
├─ _개발자료/_design/            이 스킬의 관계도·흐름도
└─ CHANGELOG.md        이력
```

- 학생·처음 쓰는 사람: §1 원칙 → §3 표를 위에서부터. 각 행의 「읽을 것/복사할 것」만 열면 된다. 다른 에이전트 원본을 찾을 필요 없다 — 필요한 구성은 전부 여기 옮겨져 있다.
- 산출물 = 에이전트 폴더(§6). 완성도 높은 실물 에이전트의 구조를 그대로 따른다.

## §1. 원칙 9 (어기면 출하 무효)

1. **역할 고정** — 나는 제조자다. 에이전트가 할 일(문서·논문·판정)을 대신 하지 않는다. 시운전은 1회, 제품 내부 지표(점수·라운드)를 PO 에게 중계하지 않는다.
2. **자기검증 금지** — 만든 사람이 자기 결과를 통과시키지 않는다. 검증자는 Phase 7 에서만 부른다(중간 라운드 없음).
3. **뼈대 복제** — 데스크톱형 GUI 는 `templates/gui_skeleton/index.html`·`ui_skeleton.py` 를 복사해 `{{ }}` 만 채운다. 블록 이동·삭제·접기 변경 금지. 자리 표시 어휘(접수·작업·사건)는 도메인 사람의 말로 전부 바꾼다.
4. **LLM 두 자리** — 작업·1차 검증 = Claude Code CLI, 2차 검증 = Codex CLI. 다른 CLI 를 끼워 넣지 않는다. 제작·검증·로컬 런타임은 구독, API 키는 웹사이트형 서버에만.
5. **미확인 ≠ 통과, 정의됨 ≠ 호출됨** — 설치 확인은 작동 확인이 아니다(칩 4값). 문서에 «구현했다»고 적은 함수는 코드에 있고 다른 곳에서 불려야 한다(시험이 잡는다). LLM 「1차·2차 검증」은 칩이 아니라 `verify_1st`·`verify_2nd` 호출이 있어야 검증이다.
6. **설계도는 구현과 같아야 출하** — 구현이 설계와 달라지는 순간 SVG·plan 을 고치고, Phase 6 마감에 화면 단계 ↔ 흐름도 1:1 을 대조한다.
7. **상태를 지우는 경로는 확인 + 백업** — 초기화 전 백업, 단계마다 스냅샷. 검증자 소환 전에도 스냅샷.
8. **외부 의존은 정확히 2개** — `mbo-천상`(목표·승인·보고, 없으면 자동 설치) · `Codex`(V2, 없으면 Opus 5 Teammate 폴백). 그 외 스킬은 있으면 쓰고 없으면 본문 폴백.
9. **PO 게이트 2개만** — Phase 2 목표서 승인 · Phase 2.5 리서치 깊이(경로 B). 나머지는 자율. 결함·안건은 한 번에 하나씩.

## §2. 편제

| 역할 | 주체 | 모델 | 규칙 |
|---|---|---|---|
| 작성자 | 이 스킬을 실행하는 세션 | Opus 5 | Phase 0~9 전담. 자기 검증 금지 |
| V1 | Claude Code Teammate(제조 미참여) | Sonnet 5 | 읽기전용 · **상태 변경 함수·라우트·CLI 호출 금지** · 산출물+기준만 전달 · `templates/V1_지시서.md` 로 소환 |
| V2 | Codex CLI (L 규모만) | gpt-5.6-terra | 읽기전용 샌드박스 · `templates/V2_지시서.md` · 탐지 실패 시 Opus 5 Teammate 폴백(보고서에 기록) |

소환은 Phase 7 단 1곳. 반려 항목은 수정 후 **그 항목만 「소거됨/잔존」 이진 재확인**(재채점·재라운드 없음). 상세 `docs/50`.

## §3. Phase 표 — 입력 / 할 일 / 산출물 파일 / 게이트 / 읽을 것

| Phase | 입력 | 할 일(요지) | 산출물(파일) | 게이트 → 다음 | 읽을 것 / 복사할 것 |
|:-:|---|---|---|---|---|
| **0 시동** | PO 요청 한 줄 | ① `mbo-천상` 확인·없으면 설치·검증 ② 역할 선언 1줄 ③ 경계 트리(Claude Code 안에서만? → `/skill-create`) ④ 작업 폴더 | 대화 기록 | mbo 연결 ✅ 폴더 확정 ✅ | `docs/10` §Phase 0 |
| **1 요구 발굴** | 폴더 | 12항목 문답(초보자 친화 4규칙) → **분기 3개 결정**(§4) → plan 초안 + 관계도·흐름도 초안 | `_개발자료/_design/plan.md` · `{이름}_architecture.svg` | plan 12항목 빈칸 0 | `docs/00` `docs/10` · `templates/양식/plan.md` |
| **2 목표 정의** | plan | `/mbo-천상` 호출 → 목표서(+「제조 대상: 7요소+메타」 삽입 절) → ⛔ PO 승인 | `{날짜}_mbo-천상_{이름}.md` | PO "승인" | `docs/20` §목표서 삽입 절 |
| **2.5 리서치** *(경로 B만)* | 목표서 | 4트랙 광역 조사(S 8/M 20/L 40건, L 은 Subagent 병렬) → 1장 요약 → ⛔ PO 깊이 게이트 1회 | `_개발자료/_design/phase_2.5_research_{날짜}.md` + `research_raw/` | PO OK | `docs/15` |
| **3 발굴** | 목표서(+리서치) | A: 원자재를 입고 카드로 분해 / B: 공개 저장소·OSS·HF·사내 자산 카탈로그 → 라이선스 게이트 | 카탈로그 / 입고 카드 | 후보 ≥3 또는 🏭 선언 | `docs/10` §발굴 2경로·라이선스 |
| **4 BOM** | 카탈로그 | 5대 KPI 채점 → 부품 분해 → 안전성 진단 → 5분류 🟢🟡🔴🏭🔵 | `bom.md` · `SOURCE_REUSE_LOG.md` · `THIRD_PARTY_NOTICES.md` | 🔴 분리 ✅ | `docs/20` §BOM · `templates/양식/bom.md` |
| **5 자체 점검** | plan·svg·bom | 5A 루브릭 셀프 채점 1회(5B 진단은 M·L) — 검증자 없음 | `_개발자료/_design/phase5_selfcheck.md` | 80 미만이면 PO 보고 | `docs/20` §자체 점검 |
| **6 조립** | BOM | **공통**(폴더·헌법·SSOT·`templates/*_skeleton.py` 5개 복사→도메인 채움·uicontract·시험) → **트랙**(GUI: 뼈대 복사→{{ }}→어휘→고정표 자기 대조→ui.py→시작.bat / 비GUI: run.py 명령 4 / 웹: 페이지) → **설계도 갱신** → 대조표 | `app/*` · `시작.bat` · `CLAUDE.md` · 문서 4종 · `_개발자료/tests/` · (GUI) `_개발자료/_qc/smoke_ui.py` · `기획안_구현_대조표.md` · SVG 최종 | `checklists/phase_gates` 6→6b 전항 | `docs/30` + (`docs/31` 또는 `docs/32`) + `docs/40` · `templates/*` 전부 |
| **6b 시운전** | 조립본 | 사용자 여정 **1회**(약식·샘플 모드) — 결함은 고치되 재실행은 여정이 끊겼을 때만 | state·산출물 파일 | 여정 완주 증거 | `docs/30` §시운전 |
| **7 출하 검사** 🔍 | 조립본+시운전 | 스냅샷 → **V1 1회**(4단 QC·6축·고정표·SVG↔화면·시작.bat 실기동) → 합격선 판정 → 불합격은 항목 이진 재확인 → **L 이면 V2 1회** | `_개발자료/_qc/pre_verify_snapshot/` · `v1_report.md` · `v1_gui_대조표.md` · `v2_report.md` | §5 합격선 | `docs/50` · `templates/V1_지시서` `V2_지시서` · `checklists/v1_v2_대조표` `gui_고정표` |
| **8 출하** | PASS | `출하_정리.py --지움` → 등재 → 헌법 확인 → 출하 보고서 → `/mbo-천상 report` → (학생 배포면 `--포장`) | `_개발자료/_qc/출하_보고서.md`(양식) · 자산 등재 1줄(제작자 레지스트리 또는 `_개발자료/자산_등재.md`) · MBO 결과 보고 | 보고서 완료 | `docs/60` §Phase 8 |
| **9 운영** | 로그·피드백 | 트리거 감지 → 수리계약서(항목·수리·대조·이진 확인) → 회귀 깊이 표로 Phase 복귀 | 수리계약서 N | 무한 루프 | `docs/60` §Phase 9 |

산출물 파일명은 이 표와 `checklists/phase_gates.md` 가 단일 출처.

## §4. 분기 트리 3개 (Phase 1 끝에 전부 결정, plan §1 좌표에 적는다)

```
① 원자재      가져온 선행 에이전트·코드·문서가 있나?
              ├─ 예 → 경로 A: 그것만 분해·조립. Phase 2.5·3 공개 발굴 생략. 부족 부품은 🏭 자체 제작(밖에서 가져오려면 PO 승인 후 1건만)
              └─ 아니오 → 경로 B: Phase 2.5 리서치 + Phase 3 공개 발굴
② 트랙        구동 방식 + 사용자 층
              ├─ 웹사이트형 ───────────────────────────→ docs/32 §B (페이지 = UI, 서버 API 키)
              ├─ 데스크톱형 + 인프라 B + 사용자가 개발자 아님 → GUI 트랙: docs/31 + templates/gui_skeleton·ui_skeleton (고정표·어휘·대조 전부 의무)
              └─ 개발자 본인 내부 도구 / 자동화 데몬 ──→ 비GUI 트랙: docs/32 §A (run.py 명령 4개)
③ 규모        S: 부품 ≤2·≤300행·UI 없음·배포 아님  /  M: 그 사이  /  L: 배포형·포털·UI 다수·부품 6+·1500행+
              ├─ L → Phase 2.5 Subagent 병렬 · 시험 150건+ · Phase 7 V2 의무
              └─ S·M → 작성자 직접 리서치 · 시험 20/60건+ · V1 만
```
경계(Phase 0): 「Claude Code 안에서만 도는 절차·체크리스트」면 이 공장이 아니라 `/skill-create` 다.

## §5. 합격 판정 (7-5)

V1·V2 는 **6축 100점**(사실 정확성 15 · 용어 일관성 15 · 구조 완성도 15 · 규칙 준수 15 · 실용성 15 · 사양 충족률 25)을 매기고, **4단 QC**(7-1 정적 · 7-2 동적 · 7-3 클릭/실기동 · 7-4 가드 시뮬)를 O/X 로 따로 판정한다.

**합격 = 총점 ≥ 95 AND Critical·High 0 AND 4단 전항 O AND (GUI) 고정표 X 0 AND 사용자 여정 KPI O.**
불합격 → 작성자 수정 → 검증자에게 **그 항목만** 「소거됨/잔존」 → 잔존이면 Phase 6 회귀. V2 는 L 만, `|V1−V2| > 3` 이면 V2 결함 수정 후 항목 재확인. Medium·Low 는 Phase 9 백로그. 제품 내부 자가 점검 점수는 출하 판정 권한이 없다. 상세 `docs/50`.

## §6. 산출물 = 에이전트 폴더 (이 모양이 아니면 조립이 끝난 것이 아니다)

```
{{폴더}}/
├─ 시작.bat                       사용자가 누르는 유일한 파일 (ASCII·CRLF·BOM 없음·echo 괄호 없음)
├─ CLAUDE.md                      헌법 + 반복된 함정 + 고칠 때 명령 (templates/CLAUDE.md)
├─ README.md · 사용자 매뉴얼(설치 및 사용법).html · 이번에 바뀐 것.md · 확인이 필요한 사항 목록.md
├─ SOURCE_REUSE_LOG.md · THIRD_PARTY_NOTICES.md
├─ app/                           본체 — 사용자는 열 일 없음
│  ├─ engine.py (State Machine+액션봇) · store.py (원자 쓰기·잠금·스냅샷·백업) · llm.py (claude→codex) · guard.py
│  ├─ uicontract.py · setup_helper.py · ui.py · ui/index.html   ← GUI 트랙   /  run.py ← 비GUI 트랙(GUI 트랙도 병행)
│  ├─ skills/*.md (규칙 SSOT) · config/ · vault/ · uploads/ · output/ · logs/ · state.json · state_backups/
└─ _개발자료/                     실무자 눈에 안 띄게
   ├─ _design/ plan.md · {이름}_architecture.svg · bom.md · phase5_selfcheck.md · 기획안_구현_대조표.md (· phase_2.5_research)
   ├─ _qc/ 출하_보고서.md · v1_report · v1_gui_대조표 · v2_report · 캡처 · pre_verify_snapshot/
   ├─ tests/ test_gates.py … (S 20 / M 60 / L 150)   ·   tools/ 출하_정리.py · verify_windows_adapter.ps1   ·   manual/
```
7대 구성요소는 전부 파일로 존재해야 한다: 🎭 `skills/persona.md` · 🎯 목표(state·설정·우측 목표 블록) · 🤖 `llm.py` · 📘 `skills/*`·`vault/`·API · 🔧 도구 모듈(코드 계산 우선) · 🛡️ `guard`·게이트·상한·백업 · 🔁 `engine` 루프.

## §7. 금지 (하면 Phase 7 에서 High)

- 뼈대를 안 쓰고 화면을 새로 짜는 것 · 블록을 다른 기둥으로 옮기는 것 · 좌측에 목표/안전 체계/설정을 두는 것 · LLM 4번째 자리
- 화면·로그에 「액션봇」 등 제조 용어 노출(사용자에게는 「AI 대화」「AI」) · 자리 표시 어휘(접수·사건·작업)를 그대로 두는 것
- `시작.bat` 에 한글·비ASCII 폴더명·echo 괄호 · `python app/ui.py` 직접 실행으로 진입점 검증을 대신하는 것
- 검증자가 상태를 바꾸는 함수를 부르는 것 · 검증 전 스냅샷 없이 소환 · 중간 Phase 에서 검증자 소환 · 재라운드
- 설계도(SVG·plan) 를 갱신하지 않고 출하 · 흐름도에 안 만든 기능을 남기는 것
- 시운전 2회 이상 · 제품 내부 점수 중계 · 원자재가 있는데 공개 발굴로 새는 것
- 발굴 원본 클론(`_scratch/`)을 출하물에 남기는 것(타인 API 키가 실려 나간 실사고) · 시험 데이터 미정리 출하

## §8. 도구·짝 스킬

- 도구: AskUserQuestion(문답·승인) · Read/Glob/Grep · WebSearch/WebFetch(경로 B) · Bash(설치 curl · `codex --version` · `codex exec -m gpt-5.6-sol "reply OK"` → 실패 시 `-m gpt-5.6-terra` · Playwright) · Write/Edit · Agent(V1·V2 폴백 Teammate) · Skill(`/mbo-천상` 필수 · `/diagram-기본` 선택)
- 짝: `/skill-create-코어5`(Claude Code 안에서만 도는 절차) · `/A판-에신`(A-Pan 판매용 강화판) · `/에신-라이트`(PO 개인 미니 도구·교육용 요약판)
- 이력: `CHANGELOG.md` · 구본: `_archive/SKILL_v3.27.md` · 부록: `docs/90_부록_구본_개요.md`
