#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

Write-Host "=== PASSO 0: GIT CHECKPOINT ===" -ForegroundColor Green
Write-Host ""

# 1. Git status
Write-Host "1. Verificando git status..." -ForegroundColor Cyan
$status = git status --porcelain
if ($status) {
    Write-Host "Arquivos modificados encontrados:" -ForegroundColor Yellow
    Write-Host $status
} else {
    Write-Host "Working tree clean (sem mudanças pendentes)" -ForegroundColor Green
}
Write-Host ""

# 2. Branch atual
Write-Host "2. Branch atual:" -ForegroundColor Cyan
$branch = git branch --show-current
Write-Host "Branch: $branch" -ForegroundColor Green
Write-Host ""

# 3. Fazer checkpoint
Write-Host "3. Fazendo checkpoint..." -ForegroundColor Cyan
git add .
$commitMsg = "chore: checkpoint antes da padronizacao global das listas"

try {
    git commit -m $commitMsg 2>&1 | Tee-Object -Variable commitOutput
    Write-Host "Checkpoint criado com sucesso!" -ForegroundColor Green
} catch {
    if ($_ -match "nothing to commit") {
        Write-Host "Nenhuma mudança pendente (working tree clean)" -ForegroundColor Green
    } else {
        throw $_
    }
}
Write-Host ""

# 4. Backup do DB
Write-Host "4. Fazendo backup do database..." -ForegroundColor Cyan
if (Test-Path "db.sqlite3") {
    Copy-Item "db.sqlite3" "db.sqlite3.bak" -Force
    Write-Host "Backup criado: db.sqlite3.bak" -ForegroundColor Green
}
Write-Host ""

# 5. Sumário
Write-Host "=== PASSO 0 CONCLUÍDO ===" -ForegroundColor Green
Write-Host "Status: Pronto para começar a padronização" -ForegroundColor Green
