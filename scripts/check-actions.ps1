param(
    [string]$Repo = "parkjunhee0510/pkrich",
    [int]$Limit = 10,
    [string]$OutputPath = "",
    [string]$LogDirectory = "logs\\actions",
    [int]$FailedSummaryLimit = 3
)

$ErrorActionPreference = "Stop"
$script:LogBuffer = New-Object System.Collections.Generic.List[string]

function Write-LogLine {
    param([string]$Message)
    Write-Host $Message
    $script:LogBuffer.Add($Message) | Out-Null
}

function Save-LogBuffer {
    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $timestamp = Get-Date -Format "yyyy-MM-dd"
        $OutputPath = Join-Path $LogDirectory "$timestamp-actions-check.txt"
    }

    $directory = Split-Path -Parent $OutputPath
    if ($directory) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $script:LogBuffer | Set-Content -Path $OutputPath -Encoding UTF8
    Write-Host "Saved log output to $OutputPath"
}

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
    Write-LogLine "Authentication required."
    Write-LogLine "Use one of the following before rerunning:"
    Write-LogLine "  gh auth login"
    Write-LogLine "  `$env:GH_TOKEN='<token>'"
    Save-LogBuffer
    exit 1
}

Write-LogLine "Recent workflow runs for $Repo"
$recentRuns = gh run list -R $Repo --limit $Limit
$recentRuns | ForEach-Object { Write-LogLine $_ }

$runMetadata = gh run list -R $Repo --limit $Limit --json databaseId,conclusion,status,displayTitle,headBranch,workflowName,createdAt,updatedAt `
    | ConvertFrom-Json

$successfulRun = $runMetadata `
    | Where-Object { $_.status -eq "completed" -and $_.conclusion -eq "success" } `
    | Select-Object -First 1

if ($null -ne $successfulRun) {
    Write-LogLine ""
    Write-LogLine "Most recent successful run summary"
    Write-LogLine "  Run ID: $($successfulRun.databaseId)"
    Write-LogLine "  Workflow: $($successfulRun.workflowName)"
    Write-LogLine "  Title: $($successfulRun.displayTitle)"
    Write-LogLine "  Branch: $($successfulRun.headBranch)"
    Write-LogLine "  Created At: $($successfulRun.createdAt)"
    Write-LogLine "  Updated At: $($successfulRun.updatedAt)"

    try {
        $successfulJobs = gh run view $successfulRun.databaseId -R $Repo --json jobs | ConvertFrom-Json
        if ($successfulJobs.jobs) {
            Write-LogLine "  Jobs:"
            foreach ($job in $successfulJobs.jobs) {
                Write-LogLine "    - $($job.name): $($job.conclusion)"
            }
        }
    }
    catch {
        Write-LogLine "  Jobs: unavailable"
    }
}

$failedRun = $runMetadata `
    | Where-Object { $_.conclusion -eq "failure" -or $_.status -eq "completed" -and $_.conclusion -eq "startup_failure" } `
    | Select-Object -First 1

$recentFailedRuns = $runMetadata `
    | Where-Object { $_.conclusion -eq "failure" -or $_.status -eq "completed" -and $_.conclusion -eq "startup_failure" } `
    | Select-Object -First $FailedSummaryLimit

if ($null -eq $failedRun) {
    Write-LogLine ""
    Write-LogLine "No failed runs found in the recent history."
    Save-LogBuffer
    exit 0
}

Write-LogLine ""
Write-LogLine "Recent failed run comparison"
foreach ($run in $recentFailedRuns) {
    Write-LogLine "  - Run ID: $($run.databaseId) | Workflow: $($run.workflowName) | Title: $($run.displayTitle) | Branch: $($run.headBranch) | Updated At: $($run.updatedAt)"
}

Write-LogLine ""
Write-LogLine "Inspecting failed run: $($failedRun.databaseId)"
$failedSummary = gh run view $failedRun.databaseId -R $Repo
$failedSummary | ForEach-Object { Write-LogLine $_ }

try {
    $failedJobs = gh run view $failedRun.databaseId -R $Repo --json jobs | ConvertFrom-Json
    if ($failedJobs.jobs) {
        Write-LogLine "  Jobs:"
        foreach ($job in $failedJobs.jobs) {
            Write-LogLine "    - $($job.name): $($job.conclusion)"
        }
    }
}
catch {
    Write-LogLine "  Jobs: unavailable"
}

Write-LogLine ""
Write-LogLine "Downloading failed run log output"
$failedLog = gh run view $failedRun.databaseId -R $Repo --log-failed
$failedLog | ForEach-Object { Write-LogLine $_ }
Save-LogBuffer
