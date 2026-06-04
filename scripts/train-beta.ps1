$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"

Write-Host "Training all beta targets (auto_steps)..."
$raw = curl.exe -s -X POST "$BaseUrl/datasets/publication/train-beta"
Write-Host $raw
$result = $raw | ConvertFrom-Json

$adopted = @($result.results | Where-Object { $_.adopted -eq $true })
Write-Host ""
Write-Host "=== Summary ==="
Write-Host "trained: $($result.results.Count)"
Write-Host "adopted: $($adopted.Count)"
Write-Host "errors: $($result.errors.Count)"

if ($adopted.Count -gt 0) {
    Write-Host ""
    Write-Host "Adopted:"
    $adopted | ForEach-Object {
        Write-Host "  $($_.target) improvement=$($_.improvement_rate) profile=$($_.feature_profile)"
    }
}
