@echo off
echo [stock_briefing] Registering 3 Windows Task Scheduler triggers...

set WRAPPER=c:\Users\sk15y\claude\stock_briefing\run_brief.bat

:: Clean up old single task (if exists)
schtasks /delete /tn "stock_briefing_0800" /f >nul 2>&1

:: Clean up previous mode tasks before re-registration
schtasks /delete /tn "stock_briefing_morning" /f >nul 2>&1
schtasks /delete /tn "stock_briefing_midday" /f >nul 2>&1
schtasks /delete /tn "stock_briefing_preview" /f >nul 2>&1

:: 08:00 - morning full brief
schtasks /create /tn "stock_briefing_morning" /tr "\"%WRAPPER%\" morning" /sc daily /st 08:00 /ru "%USERNAME%" /f
if %errorlevel%==0 (echo   [OK] 08:00 morning registered) else (echo   [X] morning failed)

:: 14:00 - midday update
schtasks /create /tn "stock_briefing_midday" /tr "\"%WRAPPER%\" midday" /sc daily /st 14:00 /ru "%USERNAME%" /f
if %errorlevel%==0 (echo   [OK] 14:00 midday registered) else (echo   [X] midday failed)

:: 21:00 - pre-market preview
schtasks /create /tn "stock_briefing_preview" /tr "\"%WRAPPER%\" preview" /sc daily /st 21:00 /ru "%USERNAME%" /f
if %errorlevel%==0 (echo   [OK] 21:00 preview registered) else (echo   [X] preview failed)

echo.
echo Run now: schtasks /run /tn "stock_briefing_morning"
echo          schtasks /run /tn "stock_briefing_midday"
echo          schtasks /run /tn "stock_briefing_preview"
echo Remove:  schtasks /delete /tn "stock_briefing_morning" /f
pause
