# install_pgvector.ps1
# Copies pre-built pgvector binaries from pgvector_temp/ into your PostgreSQL
# installation.  Must be run as Administrator (script self-elevates).
#
# Before running:
#   1. Download the pgvector Windows release for your PostgreSQL version from
#      https://github.com/pgvector/pgvector/releases
#   2. Extract the archive so that the following layout exists:
#        pgvector_temp\lib\vector.dll
#        pgvector_temp\share\extension\vector.*
#   3. Right-click this script → "Run with PowerShell" (or run from a terminal)
#
# Adjust $PG_VERSION below if you are using a different PostgreSQL version.

param(
    [string]$PG_VERSION = "18"
)

# ── Self-elevate to Administrator ─────────────────────────────────────────────
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -PG_VERSION $PG_VERSION"
    exit
}

# ── Paths ─────────────────────────────────────────────────────────────────────
$SCRIPT_DIR = Split-Path -Parent $PSCommandPath
$SOURCE     = Join-Path $SCRIPT_DIR "pgvector_temp"
$PG_DIR     = "C:\Program Files\PostgreSQL\$PG_VERSION"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
if (-not (Test-Path "$SOURCE\lib\vector.dll")) {
    Write-Host "ERROR: $SOURCE\lib\vector.dll not found." -ForegroundColor Red
    Write-Host "Download pgvector from https://github.com/pgvector/pgvector/releases" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path $PG_DIR)) {
    Write-Host "ERROR: PostgreSQL directory not found: $PG_DIR" -ForegroundColor Red
    Write-Host "Re-run with: .\install_pgvector.ps1 -PG_VERSION <your_version>" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# ── Install ───────────────────────────────────────────────────────────────────
Write-Host "Installing pgvector into PostgreSQL $PG_VERSION..." -ForegroundColor Cyan

Copy-Item "$SOURCE\lib\vector.dll" "$PG_DIR\lib\vector.dll" -Force
Write-Host "  Copied vector.dll" -ForegroundColor Green

Get-ChildItem "$SOURCE\share\extension\*" | ForEach-Object {
    Copy-Item $_.FullName "$PG_DIR\share\extension\" -Force
    Write-Host "  Copied $($_.Name)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done! pgvector is installed." -ForegroundColor Green
Write-Host "Restart PostgreSQL and then run: python migrate.py" -ForegroundColor Cyan
Read-Host "Press Enter to close"
