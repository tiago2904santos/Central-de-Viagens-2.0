@echo off
cd /d %~dp0\..\..
if exist .legacy\Central-de-Viagens-2.0 (
    cd .legacy\Central-de-Viagens-2.0
    git pull
) else (
    echo Legado V2 nao encontrado. Rode scripts\dev\clone_legacy_v2.bat primeiro.
)
pause
