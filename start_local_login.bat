@echo off
chcp 65001 >nul
title Hermes - MuseAI Local Login Server (GoLogin Orbita)
cd /d "D:\hermes-main\hermes-main\museai"
echo ======================================================================
echo   Hermes MuseAI - Local Login Server (Port 8771)
echo ======================================================================
echo.
echo Server dang khoi dong tren Desktop cua ban de GoLogin Orbita
echo co the hien thi truc tiep tren man hinh cho ban nhin thay.
echo.
echo Hay DE CUA SO NAY MO, sau do mo trinh duyet:
echo   http://127.0.0.1:8770/dashboard
echo Va bam nut [Dang nhap local]!
echo ======================================================================
echo.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set GOLOGIN_HEADLESS=0
set GOLOGIN_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OGYyNDBjZWIzODgzODhlMjdiNTU1OGMiLCJ0eXBlIjoiZGV2Iiwiand0aWQiOiI2YWJjODY5NjhkYjRmYzNlMTliYmQ2YjgifQ.F7KIA_gF71S2XYWGgtsNKtwFY-nXFltLkwYG7J-sXao
.\.venv\Scripts\python.exe tools\local_login_server.py --port 8771
pause
