param(
    [string[]]$Target = @("S1 +6", "C3 +2")
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

foreach ($name in $Target) {
    Write-Host ""
    Write-Host "=== $name ==="
    $escaped = $name.Replace("'", "''")
    & .\.venv\Scripts\python.exe -c @"
from app.core.training import train_target_model

target = '$escaped'
for strategy in ['linear', 'lightgbm', 'auto']:
    result = train_target_model(target, feature_profile='auto_steps', strategy=strategy)
    e = result.evaluation
    print(
        f'{strategy:9} profile={result.feature_profile:6} model={result.model_type:9} '
        f'adopted={result.adopted} cv_mae={e.cv_mae:.2f} baseline={e.baseline_mae:.2f} '
        f'improvement={e.improvement_rate:.4f}'
    )
"@
}
