$ErrorActionPreference = "Stop"
$DopplerProject = if ($env:DOPPLER_PROJECT) { $env:DOPPLER_PROJECT } else { "all" }
$DopplerConfig = if ($env:DOPPLER_CONFIG) { $env:DOPPLER_CONFIG } else { "main" }

if (!(Test-Path ".doppler/secrets.txt")) {
    Write-Error ".doppler/secrets.txt not found."
    exit 1
}

if (-not $env:DOPPLER_TOKEN) {
    Write-Error "DOPPLER_TOKEN is not set."
    exit 1
}

$missing = @()
Get-Content ".doppler/secrets.txt" | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    
    try {
        $null = doppler secrets get $line --plain --project $DopplerProject --config $DopplerConfig 2>$null
    } catch {
        $missing += $line
    }
}

if ($missing.Count -gt 0) {
    Write-Error "Missing Doppler secrets in ${DopplerProject}/${DopplerConfig}:`n  - $($missing -join "`n  - ")"
    exit 1
}
Write-Output "All Doppler secrets are present in ${DopplerProject}/${DopplerConfig}."
