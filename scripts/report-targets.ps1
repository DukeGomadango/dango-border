$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& .\.venv\Scripts\python.exe -c @"
from app.core.availability import get_prediction_date_range
from app.core.storage import read_json
from app.core.targets import TARGETS_PATH
from app.core.training import MODEL_REGISTRY_PATH

targets = read_json(TARGETS_PATH).get('targets', [])
models = read_json(MODEL_REGISTRY_PATH).get('models', {}) if MODEL_REGISTRY_PATH.exists() else {}

print('target | status | publish | active | predict_from | predict_to | hist_to | rows')
print('-' * 105)
for row in targets:
    name = row['target']
    active = any(e.get('active') for e in models.get(name, []))
    try:
        r = get_prediction_date_range(name)
        p_from, p_to, hist_to, rows = r.min_date, r.predict_to, r.max_date, r.rows_available
    except Exception as exc:
        p_from, p_to, hist_to, rows = '-', '-', '-', str(exc)[:30]
    pub = 'Y' if row.get('publish') else 'N'
    act = 'Y' if active else 'N'
    print(f\"{name} | {row.get('status')} | {pub} | {act} | {p_from} | {p_to} | {hist_to} | {rows}\")
"@
