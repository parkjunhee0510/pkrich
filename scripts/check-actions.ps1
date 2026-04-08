param(
    [string]$Repo = "parkjunhee0510/pkrich",
    [int]$Limit = 10
)

$ErrorActionPreference = "Stop"

function Test-GhAuth {
    try {
        gh auth status | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed."
}

if (-not $env:GH_TOKEN -and -not (Test-GhAuth)) {
    Write-Host "Authentication required."
    Write-Host "Use one of the following before rerunning:"
    Write-Host "  gh auth login"
    Write-Host "  `$env:GH_TOKEN='<token>'"
    exit 1
}

Write-Host "Recent workflow runs for $Repo"
gh run list -R $Repo --limit $Limit

$failedRun = gh run list -R $Repo --limit $Limit --json databaseId,conclusion,status `
    | ConvertFrom-Json `
    | Where-Object { $_.conclusion -eq "failure" -or $_.status -eq "completed" -and $_.conclusion -eq "startup_failure" } `
    | Select-Object -First 1

if ($null -eq $failedRun) {
    Write-Host ""
    Write-Host "No failed runs found in the recent history."
    exit 0
}

Write-Host ""
Write-Host "Inspecting failed run: $($failedRun.databaseId)"
gh run view $failedRun.databaseId -R $Repo

Write-Host ""
Write-Host "Downloading failed run log output"
gh run view $failedRun.databaseId -R $Repo --log-failed
