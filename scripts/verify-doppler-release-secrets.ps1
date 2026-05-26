param()

$ErrorActionPreference = "Stop"

if (-not $env:DOPPLER_TOKEN) {
    Write-Error "DOPPLER_TOKEN is not set. Cannot verify release secrets."
    exit 1
}

$dopplerProject = if ($env:DOPPLER_PROJECT) { $env:DOPPLER_PROJECT } else { "all" }
$dopplerConfig = if ($env:DOPPLER_CONFIG) { $env:DOPPLER_CONFIG } else { "main" }

$requiredSecrets = @(
    "PYPI_TOKEN",
    "VSCE_PAT",
    "OVSX_PAT",
    "DOPPLER_GITHUB_SERVICE_TOKEN"
)

$optionalSecrets = @(
    "TEST_PYPI_TOKEN",
    "CODECOV_TOKEN",
    "NPM_TOKEN",
    "SAFETY_API_KEY"
)

Write-Output "Verifying Doppler release secrets for project: $dopplerProject, config: $dopplerConfig"

$missingRequired = $false

foreach ($secret in $requiredSecrets) {
    $val = doppler secrets get $secret --project $dopplerProject --config $dopplerConfig --plain 2>$null
    if ($LASTEXITCODE -eq 0 -and $val) {
        Write-Output "OK: $secret"
    } else {
        Write-Output "MISSING (Required): $secret"
        $missingRequired = $true
    }
}

foreach ($secret in $optionalSecrets) {
    $val = doppler secrets get $secret --project $dopplerProject --config $dopplerConfig --plain 2>$null
    if ($LASTEXITCODE -eq 0 -and $val) {
        Write-Output "OK: $secret"
    } else {
        Write-Output "MISSING (Optional): $secret"
    }
}

if ($missingRequired) {
    Write-Error "One or more required release secrets are missing from Doppler."
    exit 1
}

Write-Output "All required release secrets are present."
exit 0
