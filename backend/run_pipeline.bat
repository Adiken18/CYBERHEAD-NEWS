@echo off

cd /d "%~dp0"

echo ====================================================== >> pipeline.log
echo CYBERHEAD pipeline started: %date% %time% >> pipeline.log
echo ====================================================== >> pipeline.log

".venv\Scripts\python.exe" -m app.pipeline >> pipeline.log 2>&1

echo ====================================================== >> pipeline.log
echo CYBERHEAD pipeline finished: %date% %time% >> pipeline.log
echo ====================================================== >> pipeline.log
echo. >> pipeline.log