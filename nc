#!/usr/bin/env sh
# NameCraft AI 명령어 모음 — 사용: ./nc [명령]   (명령 없이 실행하면 메뉴, ./nc help 는 전체 목록)
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"   # WSL 에서 Windows 가상환경을 쓰는 경우
  export PYTHONUTF8=1 WSLENV="${WSLENV:+$WSLENV:}PYTHONUTF8"
  exec "$PY" "$(wslpath -w "$ROOT/scripts/tasks.py")" "$@"   # Windows python 은 /mnt/... 경로를 모름
else
  echo "[nc] 가상환경(.venv)이 없어 만듭니다..."
  python3 -m venv "$ROOT/.venv" || { echo "[nc] Python 3.12 이상과 venv 모듈이 필요합니다."; exit 1; }
  PY="$ROOT/.venv/bin/python"
fi
exec "$PY" "$ROOT/scripts/tasks.py" "$@"
