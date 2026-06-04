param(
    [int]$Limit = 0,
    [string]$Reason = "beta quality gate passed"
)

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"

Write-Host "Publication plan:"
$plan = Invoke-RestMethod -Uri "$BaseUrl/datasets/publication/plan"
$plan | ConvertTo-Json -Compress | Write-Host

$payload = @{ reason = $Reason }
if ($Limit -gt 0) {
    $payload.limit = $Limit
}

Write-Host ""
Write-Host "Promoting eligible beta targets..."
$result = Invoke-RestMethod -Uri "$BaseUrl/datasets/publication/promote-batch" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ($payload | ConvertTo-Json -Compress)

$result | ConvertTo-Json -Depth 6 | Write-Host

Write-Host ""
Write-Host "Promoted: $($result.promoted_count)"
if ($result.promoted.Count -gt 0) {
    $result.promoted | ForEach-Object { Write-Host "  $_" }
}

Write-Host ""
Write-Host "Updated plan:"
Invoke-RestMethod -Uri "$BaseUrl/datasets/publication/plan" | ConvertTo-Json -Compress | Write-Host
