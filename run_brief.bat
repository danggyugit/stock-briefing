@echo off
cd /d c:\Users\sk15y\claude\stock_briefing
C:\Python314\python.exe main.py --mode %1 >> logs\scheduler.log 2>&1
