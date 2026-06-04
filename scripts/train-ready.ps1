$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"

Write-Host "Training all publishable targets..."
$raw = curl.exe -s -X POST "$BaseUrl/models/train-all"
Write-Host $raw
$result = $raw | ConvertFrom-Json

$adopted = @($result.results | Where-Object { $_.adopted -eq $true })
$notAdopted = @($result.results | Where-Object { $_.adopted -ne $true })
$errors = @($result.errors)

Write-Host ""
Write-Host "=== Summary ==="
Write-Host "success: $($result.results.Count)"
Write-Host "adopted (active): $($adopted.Count)"
Write-Host "trained but not adopted: $($notAdopted.Count)"
Write-Host "errors: $($errors.Count)"

if ($notAdopted.Count -gt 0) {
    Write-Host ""
    Write-Host "Not adopted:"
    $notAdopted | ForEach-Object { Write-Host "  $($_.target) improvement=$($_.improvement_rate)" }
}

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Errors:"
    $errors | ForEach-Object { Write-Host "  $($_.target): $($_.error)" }
}
