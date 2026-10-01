# -*- coding: utf-8 -*-
"""출하 봉인 확인 — 에신 V4.12 templates/seal_check.py → app/seal_check.py (데스크톱형 전용)

출하_정리.py --봉인 이 app/seal_manifest.json 에 «출하 시점 파일 해시»를 적어 배포본(zip)에 함께 넣는다.
이 모듈은 **시작할 때** 그 해시와 지금 파일을 대조해, 달라진 파일이 있으면 «경고»만 낸다(실행은 막지 않는다).

⚠ 변조 방지 장치가 아니다 — 기록(매니페스트)도 같은 폴더에 있어 누가 마음먹고 고치면 같이 고칠 수 있다.
   목적은 «실수로 또는 알리지 않고 출하 뒤에 코드를 고친 것»을 눈에 보이게 하는 것이다(docs/60 수리 절차).

경고가 나오는 자리(새 패널 없음): 화면 우측 「안전 체계」 블록의 한 줄(#seal-row) + 「오늘의 작업 로그」(store.log) + 로그 파일.
"""
import hashlib, json
from pathlib import Path

MANIFEST_NAME = "seal_manifest.json"


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(app_dir: Path, include: list, exclude_names: list, exclude_files: list) -> dict:
    """규칙에 맞는 파일의 {상대경로: sha256}. include 는 app_dir 기준 glob, exclude_names 는 경로 어디든 그 이름의 폴더·파일이면 제외,
    exclude_files 는 app_dir 기준 상대경로(UI 로 바뀌는 설정 등)."""
    out = {}
    skip_files = {x.replace("\\", "/") for x in exclude_files}
    for pat in include:
        for p in app_dir.glob(pat):
            if not p.is_file():
                continue
            rel = p.relative_to(app_dir).as_posix()
            if rel == MANIFEST_NAME or rel in skip_files:
                continue
            if any(part in exclude_names for part in p.relative_to(app_dir).parts):
                continue
            out[rel] = sha256_of(p)
    return out


def check(app_dir: Path) -> dict:
    """{"state": "unsealed"|"ok"|"mismatch", "changed": [...], "added": [...], "removed": [...]}
    unsealed = 매니페스트 없음(개발 중이거나 봉인 안 한 출하본) — 경고하지 않는다. 읽기 실패도 unsealed 가 아니라 mismatch 로 알린다."""
    mf = Path(app_dir) / MANIFEST_NAME
    if not mf.exists():
        return {"state": "unsealed", "changed": [], "added": [], "removed": []}
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
        rules = m["rules"]
        sealed = m["files"]
    except Exception:
        return {"state": "mismatch", "changed": [MANIFEST_NAME + " (읽을 수 없음)"], "added": [], "removed": []}
    now = collect(Path(app_dir), rules["include"], rules["exclude_names"], rules["exclude_files"])
    changed = sorted(k for k in sealed if k in now and now[k] != sealed[k])
    removed = sorted(k for k in sealed if k not in now)
    added = sorted(k for k in now if k not in sealed)
    state = "mismatch" if (changed or removed or added) else "ok"
    return {"state": state, "changed": changed, "added": added, "removed": removed}


def message(res: dict) -> str:
    """사람 말 한 줄. 불일치가 아니면 빈 문자열."""
    if res.get("state") != "mismatch":
        return ""
    names = res["changed"] + res["added"] + res["removed"]
    shown = ", ".join(names[:3]) + (" 외 %d개" % (len(names) - 3) if len(names) > 3 else "")
    return ("출하 뒤에 바뀐 파일이 %d개 있습니다(%s). 계속 쓸 수는 있습니다. 일부러 고친 것이라면 제작자에게 알려 주세요 — "
            "변조를 막는 장치가 아니라 실수·무단 수정을 알아보는 표시입니다." % (len(names), shown))
