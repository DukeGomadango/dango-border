$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$Root = Split-Path -Parent $PSScriptRoot
$DataFile = Join-Path $Root "raw-data.xlsx"

if (-not (Test-Path $DataFile)) {
    throw "raw-data.xlsx not found at $DataFile"
}

Write-Host "1) Health check..."
$health = curl.exe -s "$BaseUrl/health"
Write-Host $health

Write-Host "2) Upload dataset..."
$uploadRaw = curl.exe -s -X POST "$BaseUrl/datasets/upload" -F "file=@$DataFile"
Write-Host $uploadRaw
$upload = $uploadRaw | ConvertFrom-Json
$jobId = $upload.job_id
if (-not $jobId) { throw "Upload failed: $uploadRaw" }

Write-Host "3) Wait for job completion..."
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    Start-Sleep -Seconds 2
    $jobRaw = curl.exe -s "$BaseUrl/datasets/jobs/$jobId"
    $job = $jobRaw | ConvertFrom-Json
    Write-Host "  attempt $i status=$($job.status) stage=$($job.stage)"
    if ($job.status -eq "completed") { break }
    if ($job.status -eq "failed") { throw "Job failed: $jobRaw" }
    if ($i -eq $maxAttempts) { throw "Job did not complete in time." }
}

if ($job.pipeline_blocked) {
    Write-Host "4) Quality gate blocked. Applying override..."
    curl.exe -s -X POST "$BaseUrl/datasets/jobs/$jobId/quality-gate/override" `
        -H "Content-Type: application/json" `
        -d '{"reason":"m1 verification override"}' | Write-Host
}

Write-Host "5) Train target S1 +6..."
$trainRaw = curl.exe -s -X POST "$BaseUrl/models/train?target=S1%20%2B6"
Write-Host $trainRaw
$train = $trainRaw | ConvertFrom-Json
if (-not $train.adopted) {
    Write-Host "WARNING: model not adopted. Prediction may fail if no active model exists."
}

Write-Host "6) Current model..."
curl.exe -s "$BaseUrl/models/current?target=S1%20%2B6" | Write-Host

Write-Host "7) Prediction..."
$predRaw = curl.exe -s "$BaseUrl/predictions?target=S1%20%2B6&date=2026-02-26"
Write-Host $predRaw

Write-Host "M1 verification finished."
