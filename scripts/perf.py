"""성능·부하 측정 (기획서 Phase 12).

실제 uvicorn 서버를 임시 DB(현재 로컬 DB 복사본 — 전체 한자 데이터 포함)로 띄워 주요 작업의 지연 시간과
동시 요청 처리를 측정한다. 사용자 데이터는 건드리지 않는다.

사용: .venv\\Scripts\\python scripts/perf.py   (결과를 마크다운 표로 출력)
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/api/v1/"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    src = ROOT / "var" / "namecraft.db"
    if not src.exists():
        sys.exit("var/namecraft.db 가 없습니다. 먼저 tasks.py import-data 를 실행하세요.")
    tmp = Path(tempfile.mkdtemp(prefix="namecraft-perf-"))
    shutil.copy(src, tmp / "perf.db")
    env = {**os.environ, "PYTHONUTF8": "1", "NAMECRAFT_VAR_DIR": str(tmp),
           "NAMECRAFT_DATABASE_URL": f"sqlite:///{(tmp / 'perf.db').as_posix()}",
           "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT / "apps" / "api")])}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "namecraft_api.main:create_app", "--factory",
                            "--host", "127.0.0.1", "--port", str(PORT), "--no-access-log", "--log-level", "warning"],
                           cwd=ROOT, env=env)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        token = (tmp / "local_token").read_text().strip()
        H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        def call(path, body=None, method=None):
            req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                         method=method or ("POST" if body is not None else "GET"), headers=H)
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read()) if "json" in r.headers.get("content-type", "") else r.read()

        def timed(fn, n=5):
            xs = []
            for _ in range(n):
                t = time.perf_counter()
                fn()
                xs.append((time.perf_counter() - t) * 1000)
            return xs

        p = call("projects", {"title": "perf", "surname_hangul": "심", "surname_hanja": "沈", "sex": "f",
                              "preferences": {"name_type": "any", "count": 30, "use_saju": True}})["data"]
        pid = p["id"]
        rows: list[tuple[str, list[float], str]] = []
        rows.append(("후보 생성 30개 (규칙 기반, 첫 생성)", timed(lambda: call(f"projects/{pid}/candidates/generate", {"provider": "none"}), 1), ""))
        call(f"projects/{pid}/birth-profiles", {"date": "2027-01-15", "time_range": ["09:00", "12:00"], "day_window": 3})
        n = len(call(f"projects/{pid}/candidates")["data"]["items"])
        rows.append((f"후보 목록·랭킹 ({n}개, 사주 해석 포함)", timed(lambda: call(f"projects/{pid}/candidates")), ""))
        cid = call(f"projects/{pid}/candidates")["data"]["items"][0]["id"]
        rows.append(("이름 상세", timed(lambda: call(f"candidates/{cid}")), ""))
        rows.append(("이름 분석", timed(lambda: call("names/analyze", {"surname_hangul": "심", "surname_hanja": "沈",
                                                                    "given_hangul": "지아", "given_hanja": "智雅"})), ""))
        rows.append(("역검색 2음절", timed(lambda: call("names/reverse-search", {"given_hangul": "지아", "surname_hanja": "沈"})), ""))
        rows.append(("역검색 3음절", timed(lambda: call("names/reverse-search", {"given_hangul": "하은별", "surname_hanja": "沈"}), 3), ""))
        rows.append(("사주 정확 시각", timed(lambda: call("saju/calculate", {"date": "2027-01-15", "time": "10:00"})), ""))
        rows.append(("사주 시간 미정(하루)", timed(lambda: call("saju/calculate", {"date": "2027-01-15"})), ""))
        rows.append(("시나리오 ±7일·3시간", timed(lambda: call("scenarios/evaluate", {"date": "2027-01-15", "time_range": ["09:00", "12:00"], "day_window": 7}), 3), ""))
        rows.append(("출생신고 점검", timed(lambda: call("finalize/check", {"surname_hangul": "심", "given_hangul": "지아", "given_hanja": "智雅"})), ""))
        rows.append(("프로젝트 내보내기", timed(lambda: call(f"projects/{pid}/export")), ""))
        rows.append(("보고서(프로젝트 요약)", timed(lambda: call("reports", {"project_id": pid, "kind": "project_summary"}), 3), ""))

        # 동시 요청: 8개 클라이언트 × 각 10회 (개인용 로컬 앱 기준의 여유 확인)
        def burst(path, body=None, workers=8, per=10):
            lat, errors = [], 0
            def one(_):
                t = time.perf_counter()
                try:
                    call(path, body)
                    return (time.perf_counter() - t) * 1000, 0
                except Exception:
                    return (time.perf_counter() - t) * 1000, 1
            t0 = time.perf_counter()
            with ThreadPoolExecutor(workers) as ex:
                for ms, e in ex.map(one, range(workers * per)):
                    lat.append(ms)
                    errors += e
            return lat, errors, workers * per / (time.perf_counter() - t0)

        load = []
        for label, path, body in (("동시 8 × 10: 이름 분석", "names/analyze", {"surname_hangul": "심", "given_hangul": "지아"}),
                                  ("동시 8 × 10: 후보 목록·랭킹", f"projects/{pid}/candidates", None),
                                  ("동시 8 × 10: 헬스체크", "health", None)):
            lat, errors, rps = burst(path, body)
            load.append((label, lat, errors, rps))

        print("| 작업 | 횟수 | 중앙값(ms) | 최대(ms) |\n|---|---:|---:|---:|")
        for label, xs, _ in rows:
            print(f"| {label} | {len(xs)} | {statistics.median(xs):.0f} | {max(xs):.0f} |")
        print("\n| 동시 요청 | 요청 수 | p50(ms) | p95(ms) | 오류 | 처리량(req/s) |\n|---|---:|---:|---:|---:|---:|")
        for label, lat, errors, rps in load:
            q = statistics.quantiles(lat, n=20)
            print(f"| {label} | {len(lat)} | {statistics.median(lat):.0f} | {q[18]:.0f} | {errors} | {rps:.1f} |")
        return 0
    finally:
        srv.terminate()
        try:
            srv.wait(10)
        except Exception:
            srv.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
