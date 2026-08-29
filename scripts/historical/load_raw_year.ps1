param(
    [Parameter(Mandatory=$true)]
    [int]$Year
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

Write-Host ""
Write-Host "============================================================"
Write-Host "QUANTLAB - RAW DATABASE LOAD $Year"
Write-Host "============================================================"
Write-Host ""

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python virtual environment introuvable : $python"
}

$today = (Get-Date).Date

if ($Year -eq $today.Year) {
    $lastMonth = $today.Month
}
else {
    $lastMonth = 12
}

$successfulMonths = 0
$failedMonths = 0

$yearSuccess = $true

for ($month = 1; $month -le $lastMonth; $month++) {

    $monthName = "$Year-$($month.ToString('00'))"

    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host "$monthName"
    Write-Host "------------------------------------------------------------"

    & $python -m scripts.historical.load_raw_month `
        --year $Year `
        --month $month

    if ($LASTEXITCODE -ne 0) {

        Write-Host ""
        Write-Host "$monthName : FAIL"

        $failedMonths++
        $yearSuccess = $false

        break
    }

    Write-Host ""
    Write-Host "$monthName : PASS"

    $successfulMonths++
}

Write-Host ""
Write-Host "============================================================"
Write-Host "YEAR $Year RAW DATABASE SUMMARY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Mois réussis       : $successfulMonths"
Write-Host "Mois en échec      : $failedMonths"
Write-Host "Dernier mois traité: $lastMonth"

Write-Host ""

if ($yearSuccess) {

    Write-Host "DATABASE RAW $Year : PASS"

    exit 0
}
else {

    Write-Host "DATABASE RAW $Year : INCOMPLETE"

    exit 1
}
