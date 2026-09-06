# QuantLab — Collaborator Installation

## Purpose

This procedure installs the QuantLab Nasdaq HALT Analytics application on a
second Windows workstation while keeping PostgreSQL credentials outside Git.

The application uses the same GitHub repository and the shared Azure
PostgreSQL DEV database.

## Prerequisites

The collaborator must have:

- Windows 10 or Windows 11;
- access to the QuantLab GitHub repository;
- Git installed;
- Python installed;
- network access to Azure PostgreSQL;
- an Azure PostgreSQL firewall rule permitting the workstation's public IP;
- a dedicated PostgreSQL application login.

The PostgreSQL administrator account must not be used by the GUI.

## 1. Clone QuantLab

From PowerShell:

```powershell
New-Item -ItemType Directory -Force C:\QuantLab | Out-Null
Set-Location C:\QuantLab

git clone https://github.com/davidlevesque01-stack/QuantLab.git
Set-Location .\QuantLab
```

Confirm the repository:

```powershell
git status
git log -1 --oneline
```

## 2. Run the automated environment setup

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_quantlab.ps1
```

The setup script:

1. validates Git and Python;
2. creates `.venv`;
3. installs the pinned dependencies from `requirements.txt`;
4. installs QuantLab in editable mode;
5. runs the test suite;
6. stores only the non-secret PostgreSQL connection values in the Windows
   user environment;
7. asks for the collaborator's PostgreSQL login.

The PostgreSQL password is not stored.

## 3. Launch the Nasdaq HALT Analytics GUI

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_nasdaq_halts.ps1
```

The launcher asks for the PostgreSQL password using a secure PowerShell prompt
and exposes it only to the application process for that execution.

The application starts with:

```text
python -m ui.nasdaq_halts.app
```

## 4. PostgreSQL environment variables

QuantLab reads:

```text
QUANTLAB_DB_HOST
QUANTLAB_DB_PORT
QUANTLAB_DB_NAME
QUANTLAB_DB_USER
QUANTLAB_DB_PASSWORD
```

The first four are persisted as Windows user environment variables by the
setup script. `QUANTLAB_DB_PASSWORD` is intentionally transient.

Reference DEV values:

```text
QUANTLAB_DB_HOST = quantlab-postgres-dev.postgres.database.azure.com
QUANTLAB_DB_PORT = 5432
QUANTLAB_DB_NAME = quantlab
```

The user value must be the collaborator's dedicated application login.

## 5. Acceptance test

After installation:

1. launch the GUI;
2. run Manual Mode for GPUS;
3. verify a known result;
4. run File Mode with a small XLSX input;
5. verify calculation progress;
6. open the batch results;
7. verify Date and Ticker remain frozen during horizontal scrolling;
8. export XLSX;
9. confirm the timestamp in the output filename;
10. confirm the XLSX header row and first two columns are frozen;
11. close and reopen the application;
12. confirm the last input directory is remembered.

## Security

Never commit or store PostgreSQL passwords in:

- Git;
- GitHub;
- Markdown;
- committed PowerShell scripts;
- committed configuration files.

Use a dedicated least-privilege application login for the collaborator.
