@echo off
cd /d "%~dp0"
python bangla_quiz.py
if errorlevel 1 (
    echo.
    echo ---- Error: could not run the quiz ----
    echo Make sure Python is installed and run this once:
    echo   pip install pandas odfpy
    echo.
    pause
)
