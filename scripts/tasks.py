"""NameCraft AI 명령어 모음 (Windows/WSL/macOS 공용).

쓰는 법:   namecraft <명령>     (WSL·macOS 에서 처음이면 ./namecraft link 로 어디서나 쓰게 등록)
           Windows: namecraft.cmd 실행 후 메뉴에서 1번 선택
메뉴:      namecraft            (번호로 고르기)
도움말:    namecraft help
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
        sys.exit(f"사용법: namecraft {usage}")
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
        sys.exit("Unihan 원천 파일이 없습니다. 먼저 `namecraft fetch-unihan` 을 실행하세요.")
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


def lan_address() -> str:
    import ipaddress
    import socket

    override = os.getenv("NAMECRAFT_LAN_IP")
    if override:
        address = ipaddress.IPv4Address(override)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            # Select the default IPv4 interface without sending a packet.
            probe.connect(("192.0.2.1", 9))
            address = ipaddress.IPv4Address(probe.getsockname()[0])
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("사용할 수 있는 Wi-Fi 주소가 없습니다.")
    return str(address)


def start_desktop_qr(code: str):
    """Serve the QR to the desktop browser over a separate loopback-only listener."""
    import html
    import json
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    port = WEB_PORT + 1

    class DesktopQR(BaseHTTPRequestHandler):
        def do_GET(self):
            embedded = self.path == "/mobile?embed=1"
            if self.path not in {"/mobile", "/mobile?embed=1"} or self.headers.get("Host") != f"127.0.0.1:{port}":
                self.send_error(404)
                return
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_error(403)
                return
            request = urllib.request.Request(
                f"{WEB_URL}/api/mobile", headers={"Cookie": f"namecraft_mobile={code}"},
            )
            status = 200
            try:
                with urllib.request.urlopen(request, timeout=15) as upstream:
                    result = json.load(upstream)
                qr = html.escape(result["qr"], quote=True)
                content = ('<p>PC와 같은 Wi-Fi에 연결한 휴대폰 카메라로 QR을 찍어 주세요.</p>'
                           f'<img src="{qr}" width="256" height="256" alt="NameCraft 휴대폰 접속 QR">')
            except (OSError, ValueError, KeyError):
                status = 503
                content = '<p>QR을 불러오지 못했어요. 잠시 뒤 <a href="/mobile">다시 확인</a>해 주세요.</p>'
            body = f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>휴대폰에서 열기 · NameCraft</title>
<style>
body {{ background: #f8faf7; color: #193629; font: 1rem/1.6 system-ui, sans-serif; }}
main {{ max-width: 28rem; margin: 10vh auto; padding: 1.75rem; border: 1px solid #dbe6dd; border-radius: 1.25rem; background: white; }}
img {{ display: block; max-width: 100%; height: auto; margin: 0 0 1rem; }}
a {{ color: #24634c; }}
</style>
<main><h1>휴대폰에서 열기</h1>{content}<a href="{WEB_URL}/dashboard">작명 홈으로</a></main></html>""".encode("utf-8")
            if embedded:
                body = f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>휴대폰 접속 QR</title>
<style>
body {{ margin: 0; font: 1rem/1.6 system-ui, sans-serif; }}
main {{ display: grid; place-items: center; padding: 1rem; }}
p {{ text-align: center; color: #385648; }}
img {{ width: 15rem; max-width: 100%; height: auto; border-radius: 1rem; outline: 1px solid #dbe6dd; }}
</style>
<main>{content if status != 200 else f'<img src="{qr}" width="256" height="256" alt="NameCraft 휴대폰 접속 QR">'}</main></html>""".encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            if embedded:
                self.send_header("Content-Security-Policy",
                                 f"frame-ancestors {WEB_URL} http://localhost:{WEB_PORT}")
            else:
                self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), DesktopQR)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def dev() -> int:
    busy = [p for p in (API_PORT, WEB_PORT) if _port_open(p)]
    if busy:
        print(f"포트 {busy} 가 이미 사용 중입니다. 이전 서버가 남아 있으면 `namecraft stop` 을 먼저 실행하세요.")
        return 1
    browser_url = WEB_URL + "/dashboard"
    web_args = WEB_CMD
    web_env = ENV.copy()
    desktop_qr = None
    if "--lan" in sys.argv[2:]:
        import secrets

        try:
            address = lan_address()
        except (OSError, ValueError) as error:
            print(f"Wi-Fi 주소를 확인할 수 없어 이 PC에서만 엽니다. ({error})")
        else:
            code = secrets.token_urlsafe(24)
            web_env.update(NAMECRAFT_LAN_CODE=code, NAMECRAFT_LAN_ORIGIN=f"http://{address}:{WEB_PORT}")
            web_args = ["dev", "-H", "0.0.0.0", "-p", str(WEB_PORT)]
            browser_url = f"{WEB_URL}/connect#{code}"
            print("같은 Wi-Fi의 휴대폰은 홈의 ‘휴대폰에서 열기’ QR로 접속할 수 있어요.")
    migrate()
    if code := web_env.get("NAMECRAFT_LAN_CODE"):
        try:
            desktop_qr = start_desktop_qr(code)
        except OSError:
            print("PC에서 QR을 바로 보는 포트가 사용 중이에요. 자동으로 열린 브라우저 탭에서 확인해 주세요.")
    api = subprocess.Popen(API_CMD, cwd=ROOT, env=ENV)
    web = subprocess.Popen(node_bin("next/dist/bin/next") + web_args, cwd=WEB, env=web_env)
    shown_url = WEB_URL if "--open" in sys.argv[2:] else browser_url
    print(f"\n  웹: {shown_url}   (종료: Ctrl+C 또는 이 창 닫은 뒤 namecraft stop)\n", flush=True)
    if "--open" in sys.argv[2:]:
        import threading
        import time
        import urllib.request
        import webbrowser

        def _open_when_ready():
            for _ in range(120):
                try:
                    urllib.request.urlopen(WEB_URL + "/dashboard", timeout=60)
                    webbrowser.open(browser_url)
                    return
                except Exception:
                    time.sleep(1)
        threading.Thread(target=_open_when_ready, daemon=True).start()
    try:
        return web.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        kill_tree(web)
        kill_tree(api)
        if desktop_qr:
            desktop_qr.shutdown()
            desktop_qr.server_close()


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


def link() -> int:
    """WSL·macOS·Linux: ~/.local/bin/namecraft 를 만들어 어느 폴더에서나 namecraft 로 실행."""
    if os.name == "nt":
        print("Windows에서는 이 폴더에서 namecraft.cmd를 실행하세요. PowerShell에서는 .\\namecraft.cmd를 사용하세요.")
        return 0
    target = Path.home() / ".local" / "bin" / "namecraft"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(ROOT / "namecraft")
    on_path = str(target.parent) in os.environ.get("PATH", "").split(os.pathsep)
    print(f"등록했습니다: {target} → {ROOT / 'namecraft'}")
    print("이제 어느 폴더에서나 'namecraft' 로 실행됩니다." if on_path
          else f"{target.parent} 가 PATH 에 없습니다. ~/.bashrc 에 export PATH=\"$HOME/.local/bin:$PATH\" 를 추가하세요.")
    print(f"해제: rm {target}")
    return 0


def bridge() -> int:
    """연결 브리지 실행 — Windows 에서는 이 venv python 으로(Windows 에 설치된 CLI 사용)."""
    return run([PY, str(ROOT / "bridge" / "namecraft_bridge.py"), *sys.argv[2:]])


def open_web() -> int:
    import webbrowser

    if not _port_open(WEB_PORT):
        print("웹 서버가 꺼져 있습니다. 먼저 `namecraft start` 를 실행하세요.")
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
        print("  DB   : 없음 — `namecraft install` 을 실행하세요.")
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
    print("  · 되돌리려면: 서버를 끄고(`namecraft stop`) var/namecraft.db 와 var/uploads 를 이 파일들로 바꾸세요.")
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
    detail: str = ""  # namecraft help <명령> 에 보여줄 자세한 설명
    examples: tuple[str, ...] = ()


TASKS: dict[str, Task] = {
    "install": Task(install, "처음", "처음 한 번: 의존성 설치 + 한자 자료 받기 + DB 준비",
        detail="""처음 설치할 때 한 번 실행합니다. 순서대로:
  1) Python 패키지(고정 버전)와 웹 패키지를 설치합니다.
  2) Unicode Unihan 한자 자료(약 8MB)를 받습니다 — 이미 받았으면 건너뜁니다.
  3) DB 를 만들고 한자 8,525자·성씨·출처 정보를 넣습니다.
인터넷 연결이 필요하며 몇 분 걸릴 수 있습니다. 다시 실행해도 기존 프로젝트 데이터는 지워지지 않습니다.""",
        examples=("namecraft install",)),
    "start": Task(dev, "실행", "API + 웹 동시 실행 (--open: 브라우저도 열기)", "[--open] [--lan]",
        detail="""앱을 실행합니다. 실행되면 브라우저에서 http://127.0.0.1:3000 을 여세요(또는 다른 창에서 namecraft open).
  · 끄기: 이 창에서 Ctrl+C
  · 창을 그냥 닫았거나 '포트가 이미 사용 중' 이라고 나오면: namecraft stop 후 다시 namecraft start
  · 같은 Wi-Fi의 휴대폰에서 쓰려면 --lan 으로 실행한 뒤 홈에서 접속 QR을 여세요.
  · 실행할 때마다 DB 구조를 최신으로 맞춥니다(migrate).""",
        examples=("namecraft start", "namecraft start --open", "namecraft start --open --lan")),
    "stop": Task(stop, "실행", "남아 있는 이 프로젝트 서버(8000·3000) 종료",
        detail="""창을 닫았는데 서버가 계속 남아 있을 때 씁니다.
포트 8000(API)·3000(웹)을 쓰는 프로그램 중 '이 프로젝트 폴더의 서버'만 골라 하위 프로세스까지 종료합니다.
같은 포트를 쓰는 다른 프로그램은 건드리지 않고 알려만 줍니다.""",
        examples=("namecraft stop",)),
    "open": Task(open_web, "실행", "브라우저로 대시보드 열기",
        detail="기본 브라우저로 http://127.0.0.1:3000/dashboard 를 엽니다. 서버가 꺼져 있으면 안내만 합니다.",
        examples=("namecraft open",)),
    "status": Task(status, "실행", "실행 상태·DB·데이터·AI 설정 요약",
        detail="""지금 상태를 한눈에 보여줍니다(아무것도 바꾸지 않음).
  · API·웹 실행 여부
  · DB 위치·크기·구조 버전(리비전)
  · 한자 수·성씨 수·공식 인명용 한자 규칙 수 (0건이면 한자 허용 여부는 '판정 불가')
  · 프로젝트·후보·업로드 수
  · AI(Ollama·Claude Code·Antigravity) 켜짐/꺼짐""",
        examples=("namecraft status",)),
    "backup-db": Task(backup_db, "데이터", "DB 파일·업로드를 backups/ 에 복사",
        detail="""DB 파일과 업로드한 자료를 backups/<날짜-시각>/ 폴더에 복사합니다. 서버가 켜져 있어도 됩니다.
  · 이름·출생정보가 들어 있는 평문 파일이므로 안전한 곳에 보관하세요.
  · 되돌리기: namecraft stop → var/namecraft.db 와 var/uploads 를 백업 파일로 바꾸기 → namecraft start
  · 화면의 '보고서 > 백업'(JSON)은 프로젝트 단위 백업, 이 명령은 파일 전체 백업입니다.""",
        examples=("namecraft backup-db",)),
    "migrate": Task(migrate, "데이터", "DB 구조 업그레이드(Alembic)",
        detail="DB 구조를 최신 버전으로 맞춥니다. 프로그램을 업데이트한 뒤 실행하세요(namecraft start 도 자동으로 실행). 실행 전 namecraft backup-db 권장.",
        examples=("namecraft migrate",)),
    "fetch-unihan": Task(fetch_unihan, "데이터", "Unicode Unihan 원천 파일 받기",
        detail="""unicode.org 에서 한자 자료(Unihan.zip)를 받아 datasets/raw/ 에 저장하고 체크섬을 보여줍니다.
받은 뒤 namecraft import-data 로 DB 에 넣어야 반영됩니다. 개인 정보는 전송하지 않습니다.""",
        examples=("namecraft fetch-unihan", "namecraft import-data")),
    "import-data": Task(import_data, "데이터", "출처·한자·성씨 데이터 적재(다시 실행해도 안전)",
        detail="""받아 둔 Unihan 자료와 성씨 시드를 DB 에 넣습니다. 같은 출처의 이전 데이터는 교체되고,
프로젝트·후보 같은 사용자 데이터는 그대로 남습니다.""",
        examples=("namecraft import-data",)),
    "import-official": Task(import_official, "데이터", "대법원 인명용 한자표(정규화 CSV) 적재", "<CSV경로>",
        detail="""대법원 인명용 한자표를 직접 검토해 만든 CSV 를 넣습니다. 이후 한자 후보가 '공식 확인 / 미수록'으로 판정됩니다.
CSV 형식(UTF-8, 첫 줄은 머리글):
    hanja,reading,effective_date,legal_basis
    沈,심,2024-06-11,가족관계의 등록 등에 관한 규칙 제37조 별표
  · hanja: 한자 한 글자 · reading: 허용 독음(한글) · effective_date: 고시·시행일 · legal_basis: 근거""",
        examples=("namecraft import-official D:\\자료\\인명용한자.csv",)),
    "test": Task(test, "검사", "전체 테스트(백엔드 + 웹 + 타입)",
        detail="모든 자동 테스트를 실행합니다(몇 분 걸림). 마지막 줄의 summary 가 api·web 모두 PASS 면 정상입니다.",
        examples=("namecraft test",)),
    "test-api": Task(test_api, "검사", "백엔드 테스트만 (pytest 옵션 전달 가능)", "[pytest 옵션]",
        detail="백엔드(pytest) 테스트만 실행합니다. 뒤에 붙인 옵션은 pytest 로 그대로 전달됩니다.",
        examples=("namecraft test-api", "namecraft test-api -k saju", "namecraft test-api -m golden")),
    "test-web": Task(test_web, "검사", "웹 테스트 + 타입 검사",
        detail="웹 화면 컴포넌트 테스트(vitest)와 TypeScript 타입 검사를 실행합니다.", examples=("namecraft test-web",)),
    "test-security": Task(test_security, "검사", "보안 테스트만",
        detail="인증 누락·로그 개인정보·업로드·AI 출력 주입 등 보안 테스트만 실행합니다.", examples=("namecraft test-security",)),
    "build-web": Task(build_web, "검사", "웹 프로덕션 빌드",
        detail="배포용 웹 빌드를 만들어 오류가 없는지 확인합니다.", examples=("namecraft build-web",)),
    "perf": Task(perf, "검사", "성능 측정(DB 복사본 사용)",
        detail="""임시 서버와 DB 복사본으로 주요 작업 속도와 동시 요청 처리를 측정해 표로 보여줍니다.
실제 데이터는 바뀌지 않습니다. 실행 중인 서버와 별개의 포트(8765)를 씁니다.""",
        examples=("namecraft perf",)),
    "audit": Task(audit, "검사", "의존성 취약점 점검(npm·pip)",
        detail="웹(npm)과 Python(pip-audit) 패키지의 알려진 보안 취약점을 점검합니다. 인터넷 연결이 필요합니다.",
        examples=("namecraft audit",)),
    "docker-up": Task(docker_up, "Docker", "Docker 로 실행(빌드 포함, 백그라운드)",
        detail="""Docker 가 설치된 경우 컨테이너로 실행합니다(이미지 빌드 포함). 데이터는 Docker 볼륨에 따로 저장되며
namecraft start 로 쓰는 var/ 의 데이터와는 별개입니다. 끄기: namecraft docker-down""",
        examples=("namecraft docker-up", "namecraft docker-down")),
    "docker-down": Task(docker_down, "Docker", "Docker 실행 종료",
        detail="namecraft docker-up 으로 띄운 컨테이너를 종료합니다(데이터 볼륨은 남음).", examples=("namecraft docker-down",)),
    "link": Task(link, "연결", "WSL·macOS: 어느 폴더에서나 namecraft 로 쓰게 등록",
        detail="""~/.local/bin/namecraft 링크를 만들어, 프로젝트 폴더로 이동하지 않아도 namecraft 명령이 동작하게 합니다.
리눅스 기본 명령과 이름이 겹치지 않습니다. 해제하려면 rm ~/.local/bin/namecraft""",
        examples=("./namecraft link", "namecraft status")),
    "bridge": Task(bridge, "연결", "연결 브리지 실행 (Claude Code·Antigravity 를 다른 곳에서 연결)", "[--lan]",
        detail="""Claude Code·Antigravity 가 설치된 컴퓨터에서 실행하는 작은 연결 프로그램입니다.
실행하면 '주소'와 '토큰'이 화면에 나옵니다 → NameCraft 설정 › 해당 AI › 연결 방식 '연결 브리지' 에 입력하세요.
  · WSL 에 설치된 CLI : WSL 에서 namecraft bridge  (Windows 앱에서 주소 http://127.0.0.1:8787)
  · 다른 PC 의 CLI   : 그 PC 에 bridge/namecraft_bridge.py 파일 하나만 복사 → python3 namecraft_bridge.py --lan
                        (같은 네트워크에서만, 토큰을 공유하지 말 것)
  · 정해진 두 CLI 만 실행하고, 토큰이 없는 요청은 거부합니다. 끄기: Ctrl+C
  · 토큰 새로 만들기: namecraft bridge --new-token""",
        examples=("namecraft bridge", "namecraft bridge --lan", "python3 namecraft_bridge.py --port 9000")),
    "help": Task(lambda: help_(), "도움말", "기본 명령 보기 (--all: 전체 목록)", "[명령 | --all]",
        detail="명령 목록을 보여줍니다. 명령 이름을 붙이면 그 명령의 자세한 설명과 예시를 보여줍니다.",
        examples=("namecraft help", "namecraft help start", "namecraft start --help")),
    # 하위 호환 별칭
    "setup": Task(setup, "기타", "의존성만 설치(pip + npm)",
        detail="Python·웹 패키지만 설치합니다(데이터는 건드리지 않음). 보통은 namecraft install 을 쓰세요.", examples=("namecraft setup",)),
    "dev": Task(dev, "기타", "start 와 같음", detail="namecraft start 와 같습니다.", examples=("namecraft dev",)),
    "dev-api": Task(dev_api, "기타", "API 만 실행", detail="API 서버(8000)만 실행합니다. 개발용.", examples=("namecraft dev-api",)),
    "dev-web": Task(dev_web, "기타", "웹만 실행", detail="웹 서버(3000)만 실행합니다. 개발용.", examples=("namecraft dev-web",)),
}

ESSENTIAL_TASKS = ("start", "status", "stop", "backup-db")
ESSENTIAL_LABELS = {
    "start": "아기 이름 짓기 시작",
    "status": "앱 실행 상태 확인",
    "stop": "앱 종료",
    "backup-db": "작명 데이터 백업",
}


RULE = "─" * 52
INDEX_LABELS = {
    "처음": "처음 설정",
    "실행": "앱 실행 및 상태",
    "데이터": "작명 데이터 및 백업",
    "검사": "테스트 및 점검",
    "Docker": "Docker 실행",
    "연결": "명령 등록 및 AI 연결",
    "도움말": "도움말",
    "기타": "개발용 명령",
}


def accent(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ or os.getenv("TERM") == "dumb":
        return text
    if os.name == "nt" and not os.getenv("WT_SESSION"):
        return text
    return f"\x1b[1;32m{text}\x1b[0m"


def heading(subtitle: str) -> None:
    print(accent(RULE))
    print(f"  {accent('NameCraft AI')}   /   {subtitle}")
    print(accent(RULE))


def print_task_index(items: list[tuple[str, Task]]) -> None:
    width = max(len(name) for name, _ in items)
    group = None
    for name, task in items:
        if task.group != group:
            group = task.group
            print(f"\n  {accent(INDEX_LABELS[group])}")
        usage = f"  ·  {task.usage}" if task.usage else ""
        print(f"    namecraft {name:<{width}}  {task.desc}{usage}")


def help_(name: str | None = None) -> int:
    if name and name != "--all":
        t = TASKS.get(name)
        if t is None:
            near = [n for n in TASKS if name in n or n in name]
            print(f"알 수 없는 명령: {name}" + (f" — 혹시: {', '.join(near)}" if near else ""))
            print("전체 목록: namecraft help --all")
            return 2
        heading("명령 도움말")
        print(f"\n  {accent(f'namecraft {name} {t.usage}'.rstrip())}")
        print(f"  {t.desc}\n")
        if t.detail:
            print(t.detail + "\n")
        if t.examples:
            print(accent("실행 예시"))
            for example in t.examples:
                print(f"  {example}")
        return 0
    if name == "--all":
        heading("전체 명령어")
        print_task_index(list(TASKS.items()))
    else:
        heading("기본 명령어")
        for command, label in ESSENTIAL_LABELS.items():
            usage = "start --open --lan" if command == "start" else command
            print(f"    namecraft {usage:<20}  {label}")
    print("\n  전체 목록   namecraft help --all")
    print("  사용법      namecraft help <명령>")
    return 0


def menu() -> int:
    heading("작업 메뉴")
    for index, command in enumerate(ESSENTIAL_TASKS, 1):
        print(f"    {index}  {ESSENTIAL_LABELS[command]}")
    print("\n  Enter로 닫기  ·  1?처럼 입력하면 사용법 보기")
    try:
        choice = input("\n  작업 번호 > ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if not choice:
        return 0
    explain = choice.endswith("?")
    choice = choice.removesuffix("?").strip().lstrip("0")
    if not choice.isascii() or not choice.isdecimal() or len(choice) > len(str(len(ESSENTIAL_TASKS))) or not 1 <= int(choice) <= len(ESSENTIAL_TASKS):
        print("올바른 번호가 아닙니다.")
        return 2
    name = ESSENTIAL_TASKS[int(choice) - 1]
    if explain:
        return help_(name)
    sys.argv[1:] = [name, "--open", "--lan"] if name == "start" else [name]
    return TASKS[name].fn()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("menu",):
        sys.exit(menu())
    if sys.argv[1] in ("help", "-h", "--help", "/?"):
        sys.exit(help_(sys.argv[2] if sys.argv[1] == "help" and len(sys.argv) > 2 else None))
    if any(a in ("-h", "--help", "/?") for a in sys.argv[2:]) and sys.argv[1] != "test-api":
        sys.exit(help_(sys.argv[1]))
    task = TASKS.get(sys.argv[1])
    if task is None:
        sys.exit(help_(sys.argv[1]))
    sys.exit(task.fn())
