@echo off
rem The bat calls itself with input coming from nul: this way Ctrl+C's
rem "Terminate batch job (Y/N)?" prompt answers itself.
if "%~1"=="--interno" goto rodar
call <nul "%~f0" --interno
goto :eof

:rodar
cd /d "%~dp0"
python main_win.py
