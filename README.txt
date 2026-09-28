QA STATUS DASHBOARD - AUTH FIXED FULL PACKAGE

SETUP
1. Open .env.
2. Replace YOUR_REAL_PAT_HERE with the real Azure DevOps PAT.
3. Save.
4. Double-click Open_Dashboard.bat.

AUTHENTICATION CHECK
The launcher now validates the PAT before loading dashboard data.
- Placeholder/missing PAT -> clear configuration error.
- HTTP 401 -> PAT not accepted / expired / invalid.
- HTTP 403 -> permission/scope problem.
- Network error -> connection/VPN/server message.
- Success -> dashboard data is loaded.

OUTPUT
Only one file is used:
QA_Status_Dashboard.html
Every successful run overwrites this same file and opens it automatically.
A failed authentication does NOT overwrite the existing dashboard.

DASHBOARD
V24 visual dashboard + V32-style Work Item drill-down:
search, State/Assigned To filters, sorting, pagination, direct Azure links,
and CSV export for filtered work items.
