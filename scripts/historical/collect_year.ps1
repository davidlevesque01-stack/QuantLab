param(
    [Parameter(Mandatory=$true)]
    [int]$Year
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

Write-Host ""
Write-Host "============================================================"
Write-Host "QUANTLAB - HISTORICAL COLLECTION $Year"
Write-Host "============================================================"
Write-Host ""

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$collector = "collectors.nasdaq_halts.src.nasdaq_historical_collector"

if (-not (Test-Path $python)) {
    throw "Python virtual environment introuvable : $python"
}

$today = (Get-Date).Date

if ($Year -eq $today.Year) {
    $lastMonth = $today.Month
} else {
    $lastMonth = 12
}

$totalExpected = 0
$totalAcquired = 0
$totalFailed = 0
$yearSuccess = $true

for ($month = 1; $month -le $lastMonth; $month++) {

$startDate = Get-Date `
    -Year $Year `
    -Month $month `
    -Day 1 `
    -Hour 0 `
    -Minute 0 `
    -Second 0 `
    -Millisecond 0

$endDate = $startDate.AddMonths(1).AddDays(-1)

    if ($Year -eq $today.Year -and $month -eq $today.Month) {
        if ($endDate -gt $today) {
            $endDate = $today
        }
    }

    $monthName = $startDate.ToString("yyyy-MM")
    $expected = ($endDate - $startDate).Days + 1
    $totalExpected += $expected

    Write-Host ""
    Write-Host "------------------------------------------------------------"
    Write-Host "$monthName"
    Write-Host "Période : $($startDate.ToString('yyyy-MM-dd')) -> $($endDate.ToString('yyyy-MM-dd'))"
    Write-Host "------------------------------------------------------------"

    & $python -m $collector `
        --start-date $startDate.ToString("yyyy-MM-dd") `
        --end-date $endDate.ToString("yyyy-MM-dd") `
        --delay-seconds 2 `
        --max-retries 3 `
        --retry-delay-seconds 5

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "$monthName : FAIL"
        $yearSuccess = $false
        break
    }

    $pattern = "tradehalts_$Year-$($startDate.ToString('MM'))-*.xml"

    $files = Get-ChildItem `
        .\collectors\nasdaq_halts\data\raw\nasdaq\historical `
        -Filter $pattern `
        -ErrorAction SilentlyContinue

    $actual = $files.Count

    if ($actual -eq $expected) {
        Write-Host "$monthName : PASS ($actual/$expected)"
        $totalAcquired += $actual
    }
    else {
        Write-Host "$monthName : INCOMPLETE ($actual/$expected)"
        $yearSuccess = $false
        $totalAcquired += $actual
        $totalFailed += ($expected - $actual)
        break
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "YEAR $Year SUMMARY"
Write-Host "============================================================"
Write-Host ""
Write-Host "Dates attendues : $totalExpected"
Write-Host "Dates acquises  : $totalAcquired"
Write-Host "Dates manquantes: $totalFailed"
Write-Host ""

if ($yearSuccess) {
    Write-Host "ANNÉE $Year : PASS"
    exit 0
}
else {
    Write-Host "ANNÉE $Year : INCOMPLETE"
    exit 1
}
