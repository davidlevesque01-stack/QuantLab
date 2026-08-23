# QuantLab — Installation and Deployment Procedure

## 1. Purpose

This document defines the reproducible installation procedure for a QuantLab development workstation.

The objective is to allow an authorized collaborator to configure a new workstation and obtain a consistent QuantLab development environment.

## 2. Current Reference Environment

Initial reference workstation:

- Operating system: Windows
- Project root: `C:\QuantLab\QuantLab`
- Source control: Git
- Remote repository: private GitHub repository `QuantLab`
- Development environment: Visual Studio Code
- Python: installed separately
- Authentication: individual GitHub account with 2FA enabled

Secrets, passwords, recovery codes, tokens, and database credentials must never be recorded in this document.

## 3. GitHub Account

Each collaborator must use an individual GitHub account.

Requirements:

- verified email address;
- Two-Factor Authentication (2FA) enabled;
- no shared account credentials.

The initial QuantLab repository is configured as private.

## 4. Git Installation

Git for Windows is installed on the workstation.

Reference installation verified with:

    git --version

Initial workstation result:

    git version 2.55.0.windows.5

## 5. Git Identity

Git identity is configured globally:

    git config --global user.name "<USER NAME>"
    git config --global user.email "<GITHUB NOREPLY EMAIL>"

The GitHub noreply address is recommended to avoid exposing the collaborator's personal email address in commit metadata.

Configuration can be verified with:

    git config --global --list

## 6. Local Repository

The QuantLab repository is cloned under:

    C:\QuantLab\QuantLab

The repository status is verified with:

    git status

Initial expected state before the first commit:

    On branch main
    No commits yet

## 7. Initial Repository Structure

The initial monorepo contains:

    collectors/
    analytics/
    database/
    shared/
    orchestration/
    tests/
    docs/

The existing Nasdaq Halt Collector is preserved separately during migration at:

    C:\QuantLab\nasdaq_halts

It must not be deleted until migration to the QuantLab monorepo has been completed and validated.

## 8. Next Installation Stages

The following stages remain to be completed:

1. Configure `.gitignore`.
2. Create initial repository documentation.
3. Perform first Git commit and push.
4. Configure GitHub Projects.
5. Add second collaborator.
6. Migrate Nasdaq Halt Collector.
7. Establish Python environment management.
8. Deploy managed PostgreSQL.
9. Configure database security and users.
10. Integrate collectors with PostgreSQL.
11. Configure automated execution.
12. Configure on-demand execution.
13. Configure backup and restore procedures.
14. Configure Microsoft collaboration environment.

## 9. GitHub Projects Configuration

A GitHub Project named `QuantLab` has been created and configured.

Workflow statuses:

- Backlog
- Ready
- In Progress
- Review / Test
- Done

Custom fields:

- Priority
- Component
- Environment
- Target date
- Owner

Initial deployment and platform tasks have been added to the project backlog.

Completed milestone:

- Configure GitHub repository

Current milestone:

- Configure GitHub Projects