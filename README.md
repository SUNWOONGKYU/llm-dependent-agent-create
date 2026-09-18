# 에신-llm-dependent-agent-create (V4.4)

Claude Code용 **"에이전트를 만드는 스킬"** ★ 별칭 **에신 (에이전트의 신)** — LLM 의존형 AI 에이전트를 9-Phase 제조 공장으로 출하한다.

> 자매 공장: **스킬 만드는 스킬** → [SUNWOONGKYU/skill-create](https://github.com/SUNWOONGKYU/skill-create)

## 무엇을 만드나
LLM(두뇌) 의존형 AI 에이전트를 9-Phase 방식으로 제조. 모든 에이전트는 페르소나·목표·LLM·지식베이스·도구·안전 체계·자율 루프 7대 요소로 구성되며, 출하 형태는 **웹사이트형**(서버에 올려 다수가 사용)·**데스크톱형**(로컬 PC 설치, 혼자 쓰거나 여러 사람이 공용 사용) 두 가지로 한정한다. 어느 쪽이든 **실행부**(LLM 호출·판단·도구 실행)·**화면부**(사람이 보는 창과 접속 주소)·**공통부**(로그인·기록·결제·LLM 대체 경로) 세 부분이 전부 필요하며, 규모는 각 부의 크기만 정한다.

사용자는 `"에신아 ~하는 에이전트 만들어줘"`처럼 별칭으로 호출 가능.

- 모드: 단일 / 배치 / 포털
- 구동 방식: 웹사이트형 / 데스크톱형
- 산출물: 운영 가능한 에이전트 자산 (코드·UI·DB·설정)

## ⚡ 가장 빠른 설치 — Claude Code에게 시키기

본인 Claude Code 세션에 아래 한 줄을 붙여넣으세요. 알아서 받아서 `~/.claude/skills/`에 설치합니다.

> **"`SUNWOONGKYU/llm-dependent-agent-create` 설치해 줘."**

## 직접 설치

### git clone (권장 — `git pull`로 갱신 쉬움)
```bash
git clone https://github.com/SUNWOONGKYU/llm-dependent-agent-create.git
# macOS·Linux
cp -r llm-dependent-agent-create/에신-llm-dependent-agent-create ~/.claude/skills/
# Windows: cp -r llm-dependent-agent-create/에신-llm-dependent-agent-create "$env:USERPROFILE\.claude\skills\"
```

### ZIP (Git 모르는 분)
1. https://github.com/SUNWOONGKYU/llm-dependent-agent-create 접속
2. 녹색 `Code` → `Download ZIP`
3. 압축 풀고 `에신-llm-dependent-agent-create` 폴더를 `~/.claude/skills/` 안으로 복사

### SKILL.md만 raw 다운로드
```bash
mkdir -p ~/.claude/skills/에신-llm-dependent-agent-create
curl -L https://raw.githubusercontent.com/SUNWOONGKYU/llm-dependent-agent-create/main/%EC%97%90%EC%8B%A0-llm-dependent-agent-create/SKILL.md \
     -o ~/.claude/skills/에신-llm-dependent-agent-create/SKILL.md
```

## 설치 확인
```bash
ls ~/.claude/skills/ | grep 에신-llm-dependent-agent-create
```
새 Claude Code 세션에서 `/에신-llm-dependent-agent-create [만들 에이전트 설명]`이 인식되면 정상. (실행 중이었다면 재시작.)

## 필수 동반 스킬 — mbo-skill

이 스킬은 **`mbo-skill`(호출 `/mbo`)에 필수 의존**한다. Phase 2 목표서 양식·PO 승인 게이트·MBO 파일 저장·Phase 8 결과 보고(`/mbo report`)가 전부 그 스킬에서 온다. 없으면 착수 전 자동 설치를 시도한다(Phase 0-0).

미리 설치해 두려면:
```bash
# Git Bash / macOS / Linux
mkdir -p ~/.claude/skills/mbo
curl -fsSL -o ~/.claude/skills/mbo/SKILL.md https://raw.githubusercontent.com/SUNWOONGKYU/mbo-skill/main/SKILL.md
```
```powershell
# Windows PowerShell
New-Item -ItemType Directory -Force "$HOME\.claude\skills\mbo" | Out-Null
Invoke-WebRequest -Uri https://raw.githubusercontent.com/SUNWOONGKYU/mbo-skill/main/SKILL.md -OutFile "$HOME\.claude\skills\mbo\SKILL.md"
```
저장소: [SUNWOONGKYU/mbo-skill](https://github.com/SUNWOONGKYU/mbo-skill)

## 동봉 문서

- `에신-llm-dependent-agent-create/docs/00_에이전트_7대_구성요소_상세.md` — 7대 구성요소(페르소나·목표·LLM·지식베이스·도구·안전 체계·자율 루프) 심화 전문. Phase 1 문답·Phase 6 조립 전 필독.
- `에신-llm-dependent-agent-create/docs/01_GUI_표준구성_템플릿.md` — 로컬 웹 GUI를 갖춘 에이전트(데스크톱형)의 표준 조립 템플릿. 실제 출하 사례 구성 분석 9절.
- 그 외 `docs/10`~`docs/90` — 시동·요구 발굴, 설계 산출물 규격, 조립, 시험, 검증·출하 검사, 출하·운영 루프 등 Phase별 상세. `SKILL.md`는 지휘 문서(순서·분기·게이트)만 담고 절차의 「어떻게」는 전부 `docs/`에 있다.

## 검증 편제

Phase 5(설계서 확정)와 Phase 7(출하 검증) 두 곳에서 각 1회, 반드시 **다른 세션**이 검증한다(자기검증 금지).

- **작성자** — 이 스킬을 실행하는 Claude Code 세션 (Opus 5)
- **Phase 5 — 설계 검증**: V1(Claude Code Teammate, 제조 미참여 별도 세션·읽기전용, Sonnet 5)이 문서(설계서·관계도/흐름도·BOM)만 읽고 이진 체크리스트 12항목을 판정. 코드 실행 없음.
- **Phase 7 — 출하 검증**: V1(Sonnet 5, 5축 100점) + V2(Codex CLI, gpt-5.6-terra, L 규모만) — 미설치·인증 실패·할당량 소진 시 Opus 5 Teammate 폴백. "구현이 설계대로인가 + 실제로 도는가"만 검사(설계 적합성은 Phase 5에서 소진).

## 핵심 원칙 (8대 철칙)
1. 발굴물 무신뢰 — 공개 저장소도 통째 신뢰 금지
2. 부품 단위 선별
3. 운용 충돌 0건 — 타협 불가
4. 스무고개 항상 강제 (10라운드 기본)
5. MBO 승인 게이트
6. 자기검증 금지 — 별도 Verification Subagent
7. "curl 200 ≠ 동작함" — 사용자 화면 직접 확인
8. 자산화·운영까지가 완료

## 라이선스
[MIT](LICENSE) — 자유롭게 fork·수정·재배포 가능.

---
🤖 Generated and maintained with Claude Code.
