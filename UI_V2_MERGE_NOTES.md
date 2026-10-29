# UI v2 integration notes

This archive combines the existing `industrial-maintenance-dashboard-fixed.zip` project with the files from `maintenance-dashboard-ui-v2.zip`.

## UI files overlaid
- `app/static/css/dashboard.css`
- `app/static/js/app.js`
- `app/static/js/dashboard-live.js`
- `app/templates/base.html`
- `app/templates/dashboard.html`
- `app/templates/demo.html`
- `app/templates/auth/login.html`
- `app/templates/equipment/list.html`
- `app/templates/equipment/form.html`
- `app/templates/equipment/detail.html`
- `app/templates/alerts/list.html`
- `app/templates/alerts/detail.html`
- `app/templates/workorders/list.html`
- `app/templates/workorders/form.html`
- `app/templates/workorders/detail.html`
- `app/templates/telemetry/list.html`

The `dashboard.html.backup` file from the UI ZIP is also included as a backup copy.

## Preserved
All other files from the fixed project archive are retained, including Flask route modules, models, requirements, tests, Docker configuration, Jenkins pipelines, Kubernetes manifests, simulator/bridge code, and deployment documentation.

## Validation status
The merged archive was assembled successfully. Automated tests could not run in this environment because Flask is not installed (`ModuleNotFoundError: No module named 'flask'`). Run the project's tests in its configured Python environment before deploying. Template endpoint names, form behavior, and telemetry polling should be checked in a local smoke test before production use.
