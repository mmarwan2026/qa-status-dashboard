# QA Status Dashboard

Azure DevOps QA Status Dashboard with Work Item Drill-down.

## Features

- Azure DevOps integration
- QA Sprint Status
- User Stories, Test Cases and Bugs metrics
- Work Item Details drill-down
- Search and filtering
- State and Assigned To filters
- Sorting and pagination
- Direct Azure DevOps Work Item links
- CSV export
- Single HTML dashboard output

## Requirements

- Windows
- Python 3
- Git
- Access to Azure DevOps Server
- Azure DevOps Personal Access Token (PAT)

## Installation

Install the required Python packages:

    pip install -r requirements.txt

## Environment Setup

The application requires an Azure DevOps Personal Access Token.

### 1. Create `.env`

Create a file named:

    .env

in the same directory as:

    QA_Status_Dashboard.py

### 2. Configure Azure PAT

Add:

    AZURE_PAT=YOUR_REAL_PAT_HERE

Replace `YOUR_REAL_PAT_HERE` with your actual Azure DevOps PAT.

Example project structure:

    QA-Dashboard/
    ├── .env
    ├── .gitignore
    ├── Open_Dashboard.bat
    ├── QA_Status_Dashboard.py
    ├── README.md
    └── requirements.txt

## Security

Never commit the `.env` file or your Azure DevOps PAT to GitHub.

The `.gitignore` file contains:

    .env

Verify that Git ignores `.env`:

    git check-ignore -v .env

Expected result:

    .gitignore:1:.env    .env

Do NOT:

- Commit `.env`
- Put the PAT inside `QA_Status_Dashboard.py`
- Put the PAT inside `Open_Dashboard.bat`
- Put the PAT inside generated HTML
- Share the PAT in screenshots or logs

## Run Dashboard

Double-click:

    Open_Dashboard.bat

Or run:

    .\Open_Dashboard.bat

The process is:

    Read .env
        ↓
    Validate Azure PAT
        ↓
    Test Azure DevOps Authentication
        ↓
    Fetch latest QA data
        ↓
    Generate/overwrite QA_Status_Dashboard.html
        ↓
    Open Dashboard

Only one HTML dashboard is maintained:

    QA_Status_Dashboard.html

Each successful execution overwrites the previous HTML file instead of creating multiple versions.

## Authentication Errors

### 401 Unauthorized

The Azure DevOps server was reached, but the PAT was not accepted.

Check:

- PAT value
- PAT expiration
- Azure DevOps access

### 403 Forbidden

Authentication was recognized, but the account/PAT does not have the required permissions.

Check:

- PAT scopes
- Project permissions
- Collection permissions

## Daily Usage

Normally you only need to double-click:

    Open_Dashboard.bat

The dashboard will retrieve the latest Azure DevOps data and open automatically.