# -*- coding: utf-8 -*-
"""출하 전 정리 — 사용자에게 보내기 «직전»에 돌린다. 에신 V4 templates/출하_정리.py → _개발자료/tools/출하_정리.py

왜 사람 손으로 하면 안 되나: 매뉴얼에 「첫 실행 전 지울 것」을 적어도 사람이 잊으면 그대로 나간다.
시제·시험 데이터가 남아 있으면 사용자의 첫 작업부터 그것이 «과거 기록»으로 프롬프트에 실린다.
순서는 「시험 → 정리 → 포장」 — 시험이 실제 폴더에 쓰므로, 정리 뒤에 시험을 돌렸으면 정리를 다시 한다.

    python _개발자료/tools/출하_정리.py            # 세기만 한다
    python _개발자료/tools/출하_정리.py --지움      # 실제로 지운다
    python _개발자료/tools/출하_정리.py --지움 --포장  # 지운 뒤 배포 zip (_개발자료 제외)
"""
import io, os, shutil, sys, zipfile, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
# ▼ 도메인: 지울 것 — 폴더는 안을 비우고, 파일은 삭제. 없는 것은 건너뜀
CLEAR_DIRS = [APP / "output", APP / "uploads", APP / "vault", APP / "logs", APP / "state_backups", APP / ".runtime", APP / "__pycache__"]
DELETE_FILES = [APP / "state.json", APP / "history.json"]
PROTECT = {"README.md", ".gitkeep"}                     # 폴더 안에서 남길 이름
EXCLUDE_FROM_ZIP = {"_개발자료", "_scratch", "__pycache__", ".git", ".runtime"}


def count():
    n = 0
    for d in CLEAR_DIRS:
        if d.exists():
            k = sum(1 for p in d.rglob("*") if p.is_file() and p.name not in PROTECT)
            print("  %-40s %d 개" % (d.relative_to(ROOT), k)); n += k
    for f in DELETE_FILES:
        if f.exists():
            print("  %-40s 1 개" % f.relative_to(ROOT)); n += 1
    return n


def clear():
    for d in CLEAR_DIRS:
        if d.exists():
            for p in sorted(d.rglob("*"), reverse=True):
                if p.is_file() and p.name not in PROTECT:
                    p.unlink()
                elif p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
    for f in DELETE_FILES:
        if f.exists():
            f.unlink()
    # 발굴 원본 클론은 출하물에 절대 남기지 않는다(타인 API 키가 들어 있던 실사고 2026-09-17)
    if (ROOT / "_scratch").exists():
        shutil.rmtree(ROOT / "_scratch", ignore_errors=True)


def pack():
    name = "%s_%s.zip" % (ROOT.name, datetime.date.today().isoformat())
    dst = ROOT.parent / name
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob("*"):
            if p.is_dir():
                continue
            if any(part in EXCLUDE_FROM_ZIP for part in p.relative_to(ROOT).parts):
                continue
            z.write(p, str(Path(ROOT.name) / p.relative_to(ROOT)))
    print("포장:", dst)


if __name__ == "__main__":
    print("출하 정리 —", ROOT)
    n = count()
    if "--지움" in sys.argv:
        clear(); print("지움:", n, "개")
        if "--포장" in sys.argv:
            pack()
    else:
        print("세기만 했습니다. 지우려면 --지움")
