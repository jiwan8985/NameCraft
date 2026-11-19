"""NameCraft AI 명령어 모음 (Windows/WSL/macOS 공용).

짧게 쓰기: 저장소 루트에서  nc <명령>   (Windows: nc.cmd / PowerShell: .\\nc <명령>, WSL·macOS: ./nc <명령>)
메뉴:      nc            (번호로 고르기)
도움말:    nc help
직접 실행: <venv python> scripts/tasks.py <명령>
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT / "apps" / "api")]),
}
PY = sys.executable
API_PORT, WEB_PORT = 8000, 3000
API_URL = f"http://127.0.0.1:{API_PORT}"
WEB_URL = f"http://127.0.0.1:{WEB_PORT}"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run(cmd: list[str], cwd: Path = ROOT) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=cwd, env=ENV)


def node_bin(script: str) -> list[str]:
    """npm 래퍼(.cmd) 없이 node로 직접 실행 — 셸 차이 회피."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        sys.exit("node를 찾을 수 없습니다. Node.js 24 LTS를 설치하세요.")
    return [node, str(WEB / "node_modules" / script)]


def npm(*args: str) -> int:
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_cmd:
        sys.exit("npm을 찾을 수 없습니다.")
    return run([npm_cmd, *args], cwd=WEB)


def arg(i: int, usage: str) -> str:
    if len(sys.argv) <= i:
        sys.exit(f"사용법: nc {usage}")
    return sys.argv[i]


# ---------------------------------------------------------------- 설치·데이터

def setup() -> int:
    return run([PY, "-m", "pip", "install", "-r", "requirements.lock"]) or npm("ci")


def migrate() -> int:
    sys.path[:0] = [str(ROOT / "backend")]
    from namecraft.config import get_settings
    from namecraft.db import migrate as m

    m.upgrade(get_settings().resolved_database_url)
    print("migrated:", get_settings().resolved_database_url)
    return 0


UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"


def _raw_unihan() -> Path | None:
    files = sorted((ROOT / "datasets" / "raw" / "SRC-UNIHAN").glob("*/Unihan.zip"))
    return files[-1] if files else None


def fetch_unihan() -> int:
    import datetime
    import hashlib
    import urllib.request

    dest = ROOT / "datasets" / "raw" / "SRC-UNIHAN" / datetime.date.today().isoformat() / "Unihan.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("download", UNIHAN_URL)
    with urllib.request.urlopen(UNIHAN_URL, timeout=120) as r:  # 공개 파일, 사용자 정보 전송 없음
        dest.write_bytes(r.read())
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    print("saved", dest, "sha256", digest)
    print("datasets/source-manifests/SRC-UNIHAN.yaml 의 checksum_sha256 과 다르면 버전 변경 — 검토 후 갱신하세요.")
    return 0


def _session():
    sys.path[:0] = [str(ROOT / "backend")]
    from sqlalchemy.orm import sessionmaker

    from namecraft.db import get_engine

    return sessionmaker(bind=get_engine())()


def import_data() -> int:
    migrate()
    from namecraft.adapters.importers.sources import sync_manifests
    from namecraft.adapters.importers.surnames import import_surname_seed
    from namecraft.adapters.importers.unihan import import_unihan

    raw = _raw_unihan()
    if raw is None:
        sys.exit("Unihan 원천 파일이 없습니다. 먼저 `nc fetch-unihan` 을 실행하세요.")
    with _session() as s:
        print("sources:", sync_manifests(s))
        print("unihan:", import_unihan(s, raw))
        print("surnames:", import_surname_seed(s))
        s.commit()
    return 0


def import_official() -> int:
    path = Path(arg(2, "import-official <정규화CSV경로>"))
    migrate()
    from namecraft.adapters.importers.scourt_hanja import import_official_csv

    with _session() as s:
        print(import_official_csv(s, path, is_sample=False))
        s.commit()
    return 0


def install() -> int:
    """처음 한 번: 의존성 설치 → Unihan 받기(없을 때만) → DB 준비·데이터 적재."""
    rc = setup()
    if rc:
        return rc
    if _raw_unihan() is None:
        rc = fetch_unihan()
        if rc:
            return rc
    return import_data()


# ---------------------------------------------------------------- 실행·종료

API_CMD = [PY, "-m", "uvicorn", "namecraft_api.main:create_app", "--factory", "--host", "127.0.0.1",
           "--port", str(API_PORT), "--reload", "--reload-dir", "backend", "--reload-dir", "apps/api",
           "--no-access-log"]  # 기본 접근 로그는 쿼리·ID 를 남김 → 앱 미들웨어가 라우트 틀만 기록
WEB_CMD = ["dev", "-H", "127.0.0.1", "-p", str(WEB_PORT)]


def kill_tree(proc: subprocess.Popen) -> None:
    """Windows에서는 terminate()가 손자 프로세스(uvicorn reload worker)를 남기므로 트리 전체 종료."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.call(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()


def dev_api() -> int:
    migrate()
    return run(API_CMD)


def dev_web() -> int:
    return run(node_bin("next/dist/bin/next") + WEB_CMD, cwd=WEB)


def dev() -> int:
    busy = [p for p in (API_PORT, WEB_PORT) if _port_open(p)]
    if busy:
        print(f"포트 {busy} 가 이미 사용 중입니다. 이전 서버가 남아 있으면 `nc stop` 을 먼저 실행하세요.")
        return 1
    migrate()
    api = subprocess.Popen(API_CMD, cwd=ROOT, env=ENV)
    web = subprocess.Popen(node_bin("next/dist/bin/next") + WEB_CMD, cwd=WEB, env=ENV)
    print(f"\n  웹: {WEB_URL}   (종료: Ctrl+C)\n", flush=True)
    try:
        return web.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        kill_tree(web)
        kill_tree(api)


def _port_open(port: int) -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _win_listeners(ports: tuple[int, ...]) -> list[dict]:
    """포트를 쓰는 프로세스와 그 부모들(이 저장소 프로세스만) — PowerShell 조회."""
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-NetTCPConnection -LocalPort {','.join(map(str, ports))} -State Listen | ForEach-Object {{"
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.OwningProcess)\";"
        "[pscustomobject]@{port=$_.LocalPort;pid=$p.ProcessId;ppid=$p.ParentProcessId;cmd=$p.CommandLine} }"
        " | ConvertTo-Json -Compress"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    if not out:
        return []
    import json

    data = json.loads(out)
    return data if isinstance(data, list) else [data]


def _win_proc(pid: int) -> dict | None:
    import json

    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' | "
                          "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"],
                         capture_output=True, text=True).stdout.strip()
    return json.loads(out) if out else None


def stop() -> int:
    """남아 있는 이 프로젝트의 개발 서버(8000·3000)를 종료. 다른 프로그램은 건드리지 않는다."""
    root = str(ROOT).lower()
    killed = 0
    if os.name == "nt":
        for l in _win_listeners((API_PORT, WEB_PORT)):
            if root not in (l.get("cmd") or "").lower():
                print(f"포트 {l['port']}: 이 프로젝트가 아닌 프로그램(PID {l['pid']}) — 건드리지 않음")
                continue
            top = l["pid"]  # 같은 저장소 프로세스인 동안 부모로 올라가 트리 전체 종료
            for _ in range(5):
                parent = _win_proc(l["ppid"]) if l.get("ppid") else None
                if not parent or root not in (parent.get("CommandLine") or "").lower():
                    break
                top, l = parent["ProcessId"], {"ppid": parent["ParentProcessId"]}
            subprocess.call(["taskkill", "/T", "/F", "/PID", str(top)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            killed += 1
    else:
        for port in (API_PORT, WEB_PORT):
            pids = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True,
                                  text=True).stdout.split()
            for pid in pids:
                args = subprocess.run(["ps", "-o", "args=", "-p", pid], capture_output=True, text=True).stdout
                if root in args.lower():
                    subprocess.call(["kill", pid])
                    killed += 1
    left = [p for p in (API_PORT, WEB_PORT) if _port_open(p)]
    print(f"종료한 서버: {killed}개 · 아직 사용 중인 포트: {left or '없음'}")
    return 0


def open_web() -> int:
    import webbrowser

    if not _port_open(WEB_PORT):
        print("웹 서버가 꺼져 있습니다. 먼저 `nc start` 를 실행하세요.")
        return 1
    webbrowser.open(WEB_URL + "/dashboard")
    return 0


def status() -> int:
    import json
    import sqlite3
    import urllib.request

    sys.path[:0] = [str(ROOT / "backend")]
    import namecraft
    from namecraft.config import get_settings

    st = get_settings()
    print(f"NameCraft AI {namecraft.__version__}")
    try:
        with urllib.request.urlopen(API_URL + "/api/v1/health", timeout=3) as r:
            h = json.loads(r.read())
        print(f"  API  : 실행 중 ({API_URL}) · DB 리비전 {h['data']['db']['revision']}")
    except Exception:
        print(f"  API  : 꺼짐")
    print(f"  웹   : {'실행 중 (' + WEB_URL + ')' if _port_open(WEB_PORT) else '꺼짐'}")
    db = st.var_dir / "namecraft.db"
    if not db.exists():
        print("  DB   : 없음 — `nc install` 을 실행하세요.")
        return 0
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    q = lambda sql: (con.execute(sql).fetchone() or [None])[0]  # noqa: E731
    def safe(sql):
        try:
            return q(sql)
        except sqlite3.Error:
            return "—"
    print(f"  DB   : {db} ({db.stat().st_size / 1e6:.1f} MB) · 리비전 {safe('SELECT version_num FROM alembic_version')}")
    print(f"  데이터: 한자 {safe('SELECT count(*) FROM hanja_characters')}자 · 성씨 "
          f"{safe('SELECT count(*) FROM surnames WHERE is_provisional = 0')}개 · 공식 인명용 한자 규칙 "
          f"{safe('SELECT count(*) FROM official_name_character_rules WHERE is_sample = 0')}건")
    print(f"  사용자: 프로젝트 {safe('SELECT count(*) FROM naming_projects')}개 · 후보 "
          f"{safe('SELECT count(*) FROM name_candidates')}개 · 업로드 "
          f"{safe("SELECT count(*) FROM imported_documents WHERE status != 'deleted'")}건")
    try:
        rows = con.execute("SELECT provider_id, enabled FROM ai_provider_settings").fetchall()
    except sqlite3.Error:
        rows = []
    ai = {p: e for p, e in rows}
    print("  AI   : " + " · ".join(f"{p} {'켜짐' if ai.get(p, p == 'ollama') else '꺼짐'}"
                                   for p in ("ollama", "claude_code", "antigravity")))
    con.close()
    return 0


def backup_db() -> int:
    """DB 파일과 업로드 폴더를 backups/<시각>/ 에 복사(SQLite 온라인 백업 — 서버 실행 중에도 일관된 복사본)."""
    import datetime
    import sqlite3

    sys.path[:0] = [str(ROOT / "backend")]
    from namecraft.config import get_settings

    st = get_settings()
    src = st.var_dir / "namecraft.db"
    if not src.exists():
        sys.exit("DB 가 없습니다.")
    dest = ROOT / "backups" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True)
    with sqlite3.connect(src) as a, sqlite3.connect(dest / "namecraft.db") as b:
        a.backup(b)
    if (st.var_dir / "uploads").exists():
        shutil.copytree(st.var_dir / "uploads", dest / "uploads")
    print(f"백업: {dest}")
    print("  · 이름·출생정보가 들어 있는 평문 파일입니다. 안전한 곳에 보관하세요.")
    print("  · 되돌리려면: 서버를 끄고(`nc stop`) var/namecraft.db 와 var/uploads 를 이 파일들로 바꾸세요.")
    return 0


# ---------------------------------------------------------------- 테스트·점검

def test_api() -> int:
    return run([PY, "-m", "pytest", *sys.argv[2:]])


def test_web() -> int:
    return run(node_bin("vitest/vitest.mjs") + ["run"], cwd=WEB) or run(
        node_bin("typescript/bin/tsc") + ["--noEmit"], cwd=WEB)


def build_web() -> int:
    return run(node_bin("next/dist/bin/next") + ["build"], cwd=WEB)


def test() -> int:
    results = {"api": test_api(), "web": test_web()}
    print("\n== summary ==", {k: "PASS" if v == 0 else "FAIL" for k, v in results.items()})
    return 1 if any(results.values()) else 0


def test_security() -> int:
    return run([PY, "-m", "pytest", "-m", "security"])


def perf() -> int:
    return run([PY, str(ROOT / "scripts" / "perf.py")])


def audit() -> int:
    rc_web = npm("audit")
    try:
        import pip_audit  # noqa: F401
    except ImportError:
        print("pip-audit 가 없습니다: <venv python> -m pip install pip-audit")
        return rc_web or 1
    return rc_web or run([PY, "-m", "pip_audit", "-r", "requirements.lock", "--progress-spinner", "off"])


def docker_up() -> int:
    return run(["docker", "compose", "up", "--build", "-d"]) or (print(f"웹: {WEB_URL}") or 0)


def docker_down() -> int:
    return run(["docker", "compose", "down"])


# ---------------------------------------------------------------- 명령 목록·도움말·메뉴

@dataclass(frozen=True)
class Task:
    fn: Callable[[], int]
    group: str
    desc: str
    usage: str = ""


TASKS: dict[str, Task] = {
    "install":         Task(install, "처음", "처음 한 번: 의존성 설치 + 한자 자료 받기 + DB 준비"),
    "start":           Task(dev, "실행", "API + 웹 동시 실행 (종료: Ctrl+C)"),
    "stop":            Task(stop, "실행", "남아 있는 이 프로젝트 서버(8000·3000) 종료"),
    "open":            Task(open_web, "실행", "브라우저로 대시보드 열기"),
    "status":          Task(status, "실행", "실행 상태·DB·데이터·AI 설정 요약"),
    "backup-db":       Task(backup_db, "데이터", "DB 파일·업로드를 backups/ 에 복사"),
    "migrate":         Task(migrate, "데이터", "DB 구조 업그레이드(Alembic)"),
    "fetch-unihan":    Task(fetch_unihan, "데이터", "Unicode Unihan 원천 파일 받기"),
    "import-data":     Task(import_data, "데이터", "출처·한자·성씨 데이터 적재(다시 실행해도 안전)"),
    "import-official": Task(import_official, "데이터", "대법원 인명용 한자표(정규화 CSV) 적재", "<CSV경로>"),
    "test":            Task(test, "검사", "전체 테스트(백엔드 + 웹 + 타입)"),
    "test-api":        Task(test_api, "검사", "백엔드 테스트만 (pytest 옵션 전달 가능)", "[pytest 옵션]"),
    "test-web":        Task(test_web, "검사", "웹 테스트 + 타입 검사"),
    "test-security":   Task(test_security, "검사", "보안 테스트만"),
    "build-web":       Task(build_web, "검사", "웹 프로덕션 빌드"),
    "perf":            Task(perf, "검사", "성능 측정(DB 복사본 사용)"),
    "audit":           Task(audit, "검사", "의존성 취약점 점검(npm·pip)"),
    "docker-up":       Task(docker_up, "Docker", "Docker 로 실행(빌드 포함, 백그라운드)"),
    "docker-down":     Task(docker_down, "Docker", "Docker 실행 종료"),
    # 하위 호환 별칭
    "setup":           Task(setup, "기타", "의존성만 설치(pip + npm)"),
    "dev":             Task(dev, "기타", "start 와 같음"),
    "dev-api":         Task(dev_api, "기타", "API 만 실행"),
    "dev-web":         Task(dev_web, "기타", "웹만 실행"),
}


def help_() -> int:
    print(__doc__)
    group = None
    for name, t in TASKS.items():
        if t.group != group:
            group = t.group
            print(f"\n[{group}]")
        print(f"  nc {name:<16}{t.usage:<14}{t.desc}")
    return 0


def menu() -> int:
    items = [(n, t) for n, t in TASKS.items() if t.group != "기타"]
    print("NameCraft AI — 실행할 작업 번호를 입력하세요 (엔터: 취소)\n")
    for i, (n, t) in enumerate(items, 1):
        print(f"  {i:>2}. {t.desc}  [nc {n}]")
    try:
        choice = input("\n번호: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if not choice:
        return 0
    if not choice.isdigit() or not 1 <= int(choice) <= len(items):
        print("올바른 번호가 아닙니다.")
        return 2
    name, t = items[int(choice) - 1]
    if t.usage.startswith("<"):
        value = input(f"{t.usage} 입력: ").strip()
        if not value:
            return 0
        sys.argv[2:] = [value]
    sys.argv[1:2] = [name]
    return t.fn()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("menu",):
        sys.exit(menu())
    if sys.argv[1] in ("help", "-h", "--help"):
        sys.exit(help_())
    task = TASKS.get(sys.argv[1])
    if task is None:
        print(f"알 수 없는 명령: {sys.argv[1]}\n")
        help_()
        sys.exit(2)
    sys.exit(task.fn())
