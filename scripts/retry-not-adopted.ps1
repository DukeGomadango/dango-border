$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# train-ready 後に auto_steps で未採用だったターゲットへ sparse を1回試す。
param(
    [string[]]$Target = @()
)

Write-Host "Retry with sparse feature profile (strategy=auto)..."

$targetsPy = "targets = []"
if ($Target.Count -gt 0) {
    $items = $Target | ForEach-Object { "'$($_.Replace("'", "''"))'" }
    $targetsPy = "targets = [" + ($items -join ", ") + "]"
}

& .\.venv\Scripts\python.exe -c @"
from app.core.storage import read_json
from app.core.targets import TARGETS_PATH
from app.core.training import MODEL_REGISTRY_PATH, train_target_model

$targetsPy
if not targets:
    targets = []
    registry = read_json(MODEL_REGISTRY_PATH) if MODEL_REGISTRY_PATH.exists() else {}
    models = registry.get('models', {})
    for row in read_json(TARGETS_PATH).get('targets', []):
        if not row.get('publish'):
            continue
        name = row['target']
        versions = models.get(name, [])
        if not versions:
            targets.append(name)
            continue
        latest = versions[-1]
        ev = latest.get('evaluation') or {}
        if not ev.get('adopted', False):
            targets.append(name)

if not targets:
    print('No publishable targets need sparse retry.')
else:
    for t in targets:
        try:
            r = train_target_model(t, feature_profile='sparse', strategy='auto')
            e = r.evaluation
            print(
                f'{t}: profile={r.feature_profile} adopted={r.adopted} model={r.model_type} '
                f'improvement={e.improvement_rate:.4f} cv_mae={e.cv_mae:.2f}'
            )
        except Exception as exc:
            print(f'{t}: ERROR {exc}')
"@
