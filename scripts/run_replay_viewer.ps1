param(
    [string]$RepoPath = "C:\QuantLab\QuantLab",
    [Parameter(Mandatory = $true)]
    [string]$Ticker,
    [Parameter(Mandatory = $true)]
    [string]$TradingDay
)

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $RepoPath ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "QuantLab virtual environment not found. Run scripts\setup_quantlab.ps1 first."
}

$requiredVariables = @(
    "QUANTLAB_DB_HOST",
    "QUANTLAB_DB_PORT",
    "QUANTLAB_DB_NAME",
    "QUANTLAB_DB_USER"
)

foreach ($name in $requiredVariables) {
    $value = [Environment]::GetEnvironmentVariable($name, "User")

    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing persistent setting: $name. Run setup_quantlab.ps1 first."
    }

    Set-Item -Path "Env:$name" -Value $value
}

$securePassword = Read-Host `
    "PostgreSQL password for $env:QUANTLAB_DB_USER" `
    -AsSecureString

$passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
    $securePassword
)

try {
    $env:QUANTLAB_DB_PASSWORD = `
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)

    if ([string]::IsNullOrWhiteSpace($env:QUANTLAB_DB_PASSWORD)) {
        throw "PostgreSQL password cannot be empty."
    }

    Set-Location $RepoPath
    & $venvPython -m ui.replay.app --ticker $Ticker --trading-day $TradingDay
}
finally {
    Remove-Item Env:\QUANTLAB_DB_PASSWORD -ErrorAction SilentlyContinue

    if ($passwordPtr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
    }
}
