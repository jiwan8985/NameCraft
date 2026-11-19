@echo off
rem 더블클릭으로 NameCraft 실행: 처음이면 설치 -> 서버 실행 -> 브라우저 열기
chcp 65001 >nul
cd /d "%~dp0"
title NameCraft AI
if not exist "var\namecraft.db" (
  echo 처음 실행이라 설치와 데이터 준비를 합니다. 몇 분 걸릴 수 있어요...
  call namecraft.cmd install || (echo 설치 중 문제가 생겼습니다. 위 메시지를 확인하세요. & pause & exit /b 1)
)
echo.
echo  NameCraft 를 실행합니다. 잠시 뒤 브라우저가 열립니다.
echo  끝내려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.
call namecraft.cmd start --open
call namecraft.cmd stop >nul 2>nul
