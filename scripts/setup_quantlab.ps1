param(
    [string]$RepoPath = "C:\QuantLab\QuantLab"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host "QuantLab - Collaborator Environment Setup"
Write-Host "============================================================"
Write-Host ""

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

Require-Command "git"
Require-Command "python"

if (-not (Test-Path $RepoPath)) {
    throw "Repository not found at '$RepoPath'. Clone QuantLab first."
}

Set-Location $RepoPath

Write-Host "Repository : $RepoPath"
git status --short
Write-Host ""

$pythonVersion = python --version
Write-Host "Python     : $pythonVersion"
Write-Host ""

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
} else {
    Write-Host "Virtual environment already exists."
}

$venvPython = Join-Path $RepoPath ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment Python not found: $venvPython"
}

Write-Host ""
Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip

Write-Host ""
Write-Host "Installing QuantLab dependencies..."
& $venvPython -m pip install -r requirements.txt

Write-Host ""
Write-Host "Installing QuantLab package in editable mode..."
& $venvPython -m pip install -e .

Write-Host ""
Write-Host "Running automated tests..."
& $venvPython -m pytest -q

if ($LASTEXITCODE -ne 0) {
    throw "QuantLab tests failed. Setup stopped."
}

Write-Host ""
Write-Host "Configuring persistent non-secret PostgreSQL settings..."

[Environment]::SetEnvironmentVariable(
    "QUANTLAB_DB_HOST",
    "quantlab-postgres-dev.postgres.database.azure.com",
    "User"
)
[Environment]::SetEnvironmentVariable(
    "QUANTLAB_DB_PORT",
    "5432",
    "User"
)
[Environment]::SetEnvironmentVariable(
    "QUANTLAB_DB_NAME",
    "quantlab",
    "User"
)

$currentDbUser = [Environment]::GetEnvironmentVariable(
    "QUANTLAB_DB_USER",
    "User"
)

if ([string]::IsNullOrWhiteSpace($currentDbUser)) {
    $dbUser = Read-Host "PostgreSQL application login"
    if ([string]::IsNullOrWhiteSpace($dbUser)) {
        throw "PostgreSQL application login is required."
    }

    [Environment]::SetEnvironmentVariable(
        "QUANTLAB_DB_USER",
        $dbUser.Trim(),
        "User"
    )
} else {
    Write-Host "Existing PostgreSQL login retained: $currentDbUser"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "Setup completed successfully."
Write-Host ""
Write-Host "Use scripts\run_nasdaq_halts.ps1 to launch the application."
Write-Host "The PostgreSQL password is NOT stored by this setup."
Write-Host "============================================================"
Write-Host ""
