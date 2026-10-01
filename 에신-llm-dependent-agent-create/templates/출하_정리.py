# -*- coding: utf-8 -*-
"""출하 전 정리 — 사용자에게 보내기 «직전»에 돌린다. 에신 V4 templates/출하_정리.py → _개발자료/tools/출하_정리.py

왜 사람 손으로 하면 안 되나: 매뉴얼에 「첫 실행 전 지울 것」을 적어도 사람이 잊으면 그대로 나간다.
시제·시험 데이터가 남아 있으면 사용자의 첫 작업부터 그것이 «과거 기록»으로 프롬프트에 실린다.
순서는 「시험 → 정리 → 포장」 — 시험이 실제 폴더에 쓰므로, 정리 뒤에 시험을 돌렸으면 정리를 다시 한다.

    python _개발자료/tools/출하_정리.py            # 세기만 한다
    python _개발자료/tools/출하_정리.py --지움      # 실제로 지운다
    python _개발자료/tools/출하_정리.py --지움 --포장  # 지운 뒤 배포 zip (_개발자료 제외)
    python _개발자료/tools/출하_정리.py --지움 --봉인 --포장  # ★V4.12 지운 뒤 «출하 시점 해시»를 app 안에 적고 포장 (순서: 지움 → 봉인 → 포장)
    python _개발자료/tools/출하_정리.py --봉인        # 봉인만 다시(코드를 고친 뒤 재출하할 때 — docs/60 수리 절차)

봉인(★V4.12): 데스크톱형은 app/seal_manifest.json 에 소스 파일 해시를 적어 zip 에 함께 넣고, 사용자 PC 에서 시작할 때
app/seal_check.py 가 대조해 «경고»만 낸다(실행은 허용). 웹사이트형은 시작 배너가 없으니 배포 해시를 _개발자료/_qc/deploy_hash.json 에 기록하는 것으로 갈음한다.
⚠ 변조 방지가 아니다 — 실수·알리지 않은 출하 후 패치를 눈에 보이게 하는 장치다(docs/60).
"""
import io, json, os, shutil, sys, zipfile, datetime
from pathlib import Path
# Windows 한글 콘솔(cp949)에서 「—」 같은 글자로 죽지 않게(실측 2026-09-17)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
# ▼ 도메인: 지울 것 — 폴더는 안을 비우고, 파일은 삭제. 없는 것은 건너뜀
CLEAR_DIRS = [APP / "output", APP / "uploads", APP / "vault", APP / "logs", APP / "state_backups", APP / ".runtime", APP / "__pycache__"]
DELETE_FILES = [APP / "state.json", APP / "history.json"]
PROTECT = {"README.md", ".gitkeep"}                     # 폴더 안에서 남길 이름
EXCLUDE_FROM_ZIP = {"_개발자료", "_scratch", "__pycache__", ".git", ".runtime"}
# ▼ ★V4.12 봉인 규칙 — 대상: 소스(*.py·skills·ui) + «UI 에 안 나오는» config. 실행 중에 쓰는 파일과 UI 로 바뀌는 설정은 제외(제외 안 하면 정상 사용마다 경고 → 경고 피로)
DEPLOY_TYPE = "desktop"        # ▼ 도메인: "desktop" | "web" — plan.md 구동 방식. 매니페스트를 app 안에 두는 봉인은 desktop 만, web 은 배포 해시 기록으로 갈음
SEAL_INCLUDE = ["*.py", "skills/**/*", "ui/**/*", "config/**/*"]                                   # app/ 기준 glob
SEAL_EXCLUDE_NAMES = ["__pycache__", "output", "uploads", "vault", "logs", "state_backups", ".runtime"]   # 경로 어디서든 이 이름이면 제외(실행 중 쓰는 폴더)
SEAL_EXCLUDE_FILES = ["state.json", "history.json"]       # ▼ 도메인: 설정 화면(UI)이 쓰는 config 를 여기에 더한다 — 예 "config/profile.json", "config/settings.json"


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
        if (ROOT / "_scratch").exists():
            print("[경고] _scratch 를 지우지 못했습니다(열린 파일?) — 출하물에 남으면 안 됩니다. 수동 삭제 후 다시 세십시오.")
    left = count()
    if left:
        print("[경고] 지운 뒤에도 %d 개가 남았습니다 — 잠긴 파일을 확인하십시오." % left)


def _seal_rules() -> dict:
    return {"include": SEAL_INCLUDE, "exclude_names": SEAL_EXCLUDE_NAMES, "exclude_files": SEAL_EXCLUDE_FILES}


def seal():
    """★V4.12 출하 시점 해시 기록. desktop = app/seal_manifest.json(배포 zip 에 포함), web = _개발자료/_qc/deploy_hash.json(배포본 밖 기록)."""
    sys.path.insert(0, str(APP))
    try:
        import seal_check
    except ImportError:
        print("[오류] app/seal_check.py 가 없습니다 — 에신 templates/seal_check.py 를 app/ 에 복사한 뒤 다시 하십시오."); sys.exit(1)
    rules = _seal_rules()
    files = seal_check.collect(APP, rules["include"], rules["exclude_names"], rules["exclude_files"])
    if not files:
        print("[오류] 봉인 대상 파일이 0개입니다 — SEAL_INCLUDE 규칙을 확인하십시오."); sys.exit(1)
    doc = {"version": 1, "agent": ROOT.name, "sealed_at": datetime.datetime.now().isoformat(timespec="seconds"), "rules": rules, "files": files}
    if DEPLOY_TYPE == "web":
        dst = ROOT / "_개발자료" / "_qc" / "deploy_hash.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
    else:
        dst = APP / seal_check.MANIFEST_NAME
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("봉인(%s): %d 개 파일 → %s" % (DEPLOY_TYPE, len(files), dst.relative_to(ROOT)))


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
    if DEPLOY_TYPE == "desktop" and not (APP / "seal_manifest.json").exists():
        print("[경고] 봉인 매니페스트가 없는 채로 포장했습니다 — 출하 후 패치 탐지가 꺼진 배포본입니다. --봉인 을 지움 뒤·포장 앞에 넣으십시오.")


if __name__ == "__main__":
    print("출하 정리 —", ROOT)
    if "--포장" in sys.argv and "--지움" not in sys.argv:
        print("[오류] --포장 은 --지움 과 함께만 쓸 수 있습니다(시험·시제 데이터가 zip 에 실려 나가는 것을 막기 위해). 순서: --지움 --봉인 --포장"); sys.exit(2)
    n = count()
    if "--지움" in sys.argv:
        clear(); print("지움:", n, "개")
        if "--봉인" in sys.argv:
            seal()
        if "--포장" in sys.argv:
            pack()
    elif "--봉인" in sys.argv:
        seal()
    else:
        print("세기만 했습니다. 지우려면 --지움")
