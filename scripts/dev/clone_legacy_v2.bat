@echo off
cd /d %~dp0\..\..
if not exist .legacy mkdir .legacy
if exist .legacy\Central-de-Viagens-2.0 (
    echo Legado V2 ja existe em .legacy\Central-de-Viagens-2.0
    echo Para atualizar, entre na pasta e rode git pull.
) else (
    git clone https://github.com/tiago2904santos/Central-de-Viagens-2.0.git .legacy\Central-de-Viagens-2.0
)
pause
