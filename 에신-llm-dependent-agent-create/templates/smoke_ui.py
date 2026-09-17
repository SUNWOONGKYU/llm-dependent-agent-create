# -*- coding: utf-8 -*-
"""GUI 스모크 뼈대 — 에신 V4 templates/smoke_ui.py → _개발자료/_qc/smoke_ui.py (GUI 트랙 필수)
화면 구성 고정표 자기 대조(좌 4·우 7 블록 순서·접기 8개 닫힘·3단 폭) + 클릭 + 콘솔 오류 + 라이트/다크 캡처.
서버가 떠 있어야 한다(시작.bat). 실행: set PYTHONUTF8=1 && python _개발자료/_qc/smoke_ui.py
▼ 도메인: APP_SLUG·PORT·EXPECT_RIGHT(도메인 어휘로 바꾼 우측 블록 제목 7개)만 채운다.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
APP_SLUG = "{{agent-slug}}"; PORT = {{포트}}
EXPECT_LEFT = ["페르소나", "LLM", "도구", "지식베이스"]                                   # 고정
EXPECT_RIGHT = ["{{설정}}", "{{목록}}", "목표", "진행 단계 (자율 루프)", "안전 체계", "{{오늘의 기록}}", "{{대기 항목}}"]  # 어휘만 도메인
OUT = os.path.join(os.path.dirname(__file__), "")
TOKEN = open(os.path.join(os.environ["LOCALAPPDATA"], APP_SLUG, "token")).read().strip()
URL = "http://127.0.0.1:%d/?t=%s" % (PORT, TOKEN)

async def main():
    out = {}
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for scheme in ("light", "dark"):
            pg = await b.new_page(viewport={"width": 1440, "height": 900}, color_scheme=scheme); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            await pg.goto(URL); await pg.wait_for_timeout(1500)
            if scheme == "light":
                out["cols"] = await pg.evaluate("[...document.querySelectorAll('.grid > *')].map(e=>Math.round(e.getBoundingClientRect().width))")
                out["left"] = await pg.evaluate("[...document.querySelectorAll('aside.col-left > details > summary .cat-fold-title, aside.col-left > .cat-block h2')].map(e=>e.textContent.trim())")
                out["right"] = await pg.evaluate("[...document.querySelectorAll('aside.col-right > details > summary, aside.col-right > .cat-block h2')].map(e=>e.firstChild.textContent.trim())")
                out["left_ok"] = out["left"] == EXPECT_LEFT; out["right_ok"] = out["right"] == EXPECT_RIGHT
                out["folds_closed"] = await pg.evaluate("[...document.querySelectorAll('details.cat-fold')].every(e=>!e.open)")
                out["llm_rows"] = await pg.evaluate("[...document.querySelectorAll('#llm-status .plain-label')].map(e=>e.textContent)")
                out["no_actionbot_word"] = await pg.evaluate("!document.body.innerText.includes('액션봇')")
                await pg.click("#fold-persona summary"); out["persona_open"] = await pg.evaluate("document.getElementById('fold-persona').open")
                await pg.click("#fold-safe summary"); out["safe_rows"] = await pg.evaluate("[...document.querySelectorAll('#fold-safe .plain-label')].map(e=>e.textContent)")
                await pg.click("#btn-new-case"); out["workspace_shown"] = await pg.evaluate("!document.getElementById('workspace-body').hidden")
                await pg.click("#chat-open"); out["chat_open"] = await pg.evaluate("!document.getElementById('chat-panel').hidden")
                await pg.click("#chat-close")
                await pg.click("#btn-open-setup-side"); out["setup_open"] = await pg.evaluate("!document.getElementById('setup-helper').hidden")
                out["buttons_without_handler"] = await pg.evaluate("[...document.querySelectorAll('button')].filter(b=>!b.onclick && !b.id && !b.dataset.ch && !b.dataset.open && !b.closest('summary')).map(b=>b.textContent.trim()).slice(0,10)")
                await pg.click("#fold-persona summary"); await pg.click("#fold-safe summary")
            await pg.screenshot(path=os.path.join(OUT, "ui_%s.png" % scheme))
            out["console_errors_" + scheme] = [e for e in errs if "favicon" not in e]
            await pg.close()
        await b.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ok = out["left_ok"] and out["right_ok"] and out["folds_closed"] and out["llm_rows"] == ["판단·작성", "1차 검증", "2차 검증"] and out["no_actionbot_word"] \
         and not out["console_errors_light"] and not out["console_errors_dark"] and out["cols"][0] == 340 and out["cols"][2] == 344
    print("SMOKE", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
asyncio.run(main())
