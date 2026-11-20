@echo off
rem 더블클릭으로 NameCraft 실행: 처음이면 설치 -> 서버 실행 -> 브라우저 열기
chcp 65001 >nul
cd /d "%~dp0"
title NameCraft AI - 아기 이름 짓기
echo.
echo   ==================================================
echo      NameCraft AI  /  아기 이름 짓기
echo   ==================================================
echo.
if not exist "var\namecraft.db" (
  echo   처음 실행하는 중이에요. 필요한 프로그램과 이름 자료를 준비합니다.
  call namecraft.cmd install || (echo 설치 중 문제가 생겼습니다. 위 메시지를 확인하세요. & pause & exit /b 1)
)
echo.
echo   앱이 준비되면 브라우저가 열립니다.
echo   종료하려면 이 창에서 Ctrl+C 를 누르세요.
echo.
call namecraft.cmd start --open --lan
call namecraft.cmd stop >nul 2>nul
