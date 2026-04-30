@echo off
:: Continuously restarts api.py while redirecting stderr to error.log.
:start
cls
python api.py 2> error.log
echo Server wurde beendet. Starte neu in 2 Sekunden...
timeout /t 2 /nobreak > NUL
GOTO start