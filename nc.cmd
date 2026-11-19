@echo off
rem NameCraft AI 명령어 모음 — 사용: nc [명령]   (명령 없이 실행하면 메뉴, nc help 는 전체 목록)
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [nc] 가상환경^(.venv^)이 없어 만듭니다...
  where py >nul 2>nul && (py -3 -m venv "%ROOT%.venv") || (python -m venv "%ROOT%.venv")
  if not exist "%PY%" (
    echo [nc] Python 3.12 이상을 설치한 뒤 다시 실행하세요.
    exit /b 1
  )
)
"%PY%" "%ROOT%scripts\tasks.py" %*
exit /b %ERRORLEVEL%
