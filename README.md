# 에신-llm-dependent-agent-create

Claude Code용 **"에이전트를 만드는 스킬"** ★ 별칭 **에신 (에이전트의 신)** — LLM 의존형 AI 에이전트를 9-Phase 제조 공장으로 출하한다.

> 자매 공장: **스킬 만드는 스킬** → [SUNWOONGKYU/skill-create](https://github.com/SUNWOONGKYU/skill-create)

## 무엇을 만드나
LLM(두뇌) 의존형 AI 에이전트를 9-Phase 방식으로 제조. 출하 형태는 9가지 구동 방식(웹·데스크톱·모바일·메신저봇·확장·데몬·API·스케줄·포털) 중 자동 결정.

사용자는 `"에신아 ~하는 에이전트 만들어줘"`처럼 별칭으로 호출 가능.

- 모드: 단일 / 배치 / 포털
- 인프라: A (Supabase 있음) / B (DB 없음, .py + API 키)
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
