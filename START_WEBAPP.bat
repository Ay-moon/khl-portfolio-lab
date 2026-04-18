@echo off
title KHL Bank CIB Platform
echo ============================================================
echo   KHL Bank CIB Platform - Lancement
echo ============================================================
echo.
echo   URL : http://localhost:5000
echo   Pour arreter : CTRL+C
echo.
cd /d "%~dp0"
.venv\Scripts\python.exe webapp\app.py
pause
