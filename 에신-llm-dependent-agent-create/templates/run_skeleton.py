# -*- coding: utf-8 -*-
"""run.py 뼈대 (에신 V4 templates/run_skeleton.py → app/run.py) — 터미널 진입점. GUI 트랙도 병행(자동화·장애 우회·디버깅).
명령 4개 고정: start · status · resume · stop  (+ probe). 도메인 명령은 뒤에 추가.
"""
import sys, json, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine, llm, store  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("start")           # ▼ 도메인: s.add_argument("--topic", required=True) ...
    s.add_argument("--force", action="store_true")
    sub.add_parser("status"); sub.add_parser("resume"); sub.add_parser("stop")
    p = sub.add_parser("probe"); p.add_argument("--live", action="store_true")
    a = ap.parse_args()
    try:
        if a.cmd == "start":
            engine.intake(force=a.force)      # ▼ 도메인 인자 전달
            print(json.dumps(engine.run_all(), ensure_ascii=False, indent=1))
        elif a.cmd == "resume":
            print(json.dumps(engine.resume(), ensure_ascii=False, indent=1))
        elif a.cmd == "stop":
            store.update_state(lambda st: st.__setitem__("blocked", {"code": "STOPPED_BY_USER", "since": store.now_iso()}))
            print("정지 표시했습니다. 다시 시작하려면 resume.")
        elif a.cmd == "probe":
            print(json.dumps(llm.probe(live=a.live), ensure_ascii=False, indent=1))
        else:
            print(json.dumps(engine.status(), ensure_ascii=False, indent=1))
    except engine.Blocked as e:
        print("차단:", e); sys.exit(2)


if __name__ == "__main__":
    main()
