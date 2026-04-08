param(
    [string]$Repo = "parkjunhee0510/pkrich",
    [int]$Limit = 10,
    [string]$OutputPath = "",
    [string]$LogDirectory = "logs\\actions",
    [int]$FailedSummaryLimit = 3
)

$ErrorActionPreference = "Stop"
$script:LogBuffer = New-Object System.Collections.Generic.List[string]
$script:SummaryRows = New-Object System.Collections.Generic.List[object]
$script:SummaryPayload = [ordered]@{
    repo = $Repo
    generated_at = (Get-Date).ToString("s")
    successful_run = $null
    recent_failed_runs = @()
    latest_failed_run = $null
}

function Invoke-GhText {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $output = & gh @Args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (($output | Out-String).Trim())
    }
    return $output
}

function Invoke-GhJson {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $output = Invoke-GhText @Args
    $jsonText = ($output | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($jsonText)) {
        return $null
    }
    return $jsonText | ConvertFrom-Json
}

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
    Save-SummaryArtifacts
}

function Add-RunSummaryRows {
    param(
        [string]$Category,
        $RunInfo,
        $Jobs
    )

    if ($null -eq $RunInfo) {
        return
    }

    if ($Jobs -and $Jobs.jobs) {
        foreach ($job in $Jobs.jobs) {
            $script:SummaryRows.Add([pscustomobject]@{
                category = $Category
                run_id = $RunInfo.databaseId
                workflow = $RunInfo.workflowName
                title = $RunInfo.displayTitle
                branch = $RunInfo.headBranch
                status = $RunInfo.status
                conclusion = $RunInfo.conclusion
                created_at = $RunInfo.createdAt
                updated_at = $RunInfo.updatedAt
                job_name = $job.name
                job_conclusion = $job.conclusion
            }) | Out-Null
        }
        return
    }

    $script:SummaryRows.Add([pscustomobject]@{
        category = $Category
        run_id = $RunInfo.databaseId
        workflow = $RunInfo.workflowName
        title = $RunInfo.displayTitle
        branch = $RunInfo.headBranch
        status = $RunInfo.status
        conclusion = $RunInfo.conclusion
        created_at = $RunInfo.createdAt
        updated_at = $RunInfo.updatedAt
        job_name = ""
        job_conclusion = ""
    }) | Out-Null
}

function Save-SummaryArtifacts {
    $directory = [System.IO.Path]::GetDirectoryName($OutputPath)
    $filename = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    $summaryBase = if ($directory) { Join-Path $directory $filename } else { $filename }
    $jsonPath = "$summaryBase.summary.json"
    $csvPath = "$summaryBase.summary.csv"

    ($script:SummaryPayload | ConvertTo-Json -Depth 6) | Set-Content -Path $jsonPath -Encoding UTF8

    if ($script:SummaryRows.Count -gt 0) {
        $script:SummaryRows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
    }
    else {
        @() | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8
    }

    Write-Host "Saved summary JSON to $jsonPath"
    Write-Host "Saved summary CSV to $csvPath"
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

try {
    Write-LogLine "Recent workflow runs for $Repo"
    $recentRuns = Invoke-GhText run list -R $Repo --limit $Limit
    $recentRuns | ForEach-Object { Write-LogLine $_ }

    $runMetadata = Invoke-GhJson run list -R $Repo --limit $Limit --json databaseId,conclusion,status,displayTitle,headBranch,workflowName,createdAt,updatedAt

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
            $successfulJobs = Invoke-GhJson run view $successfulRun.databaseId -R $Repo --json jobs
            if ($successfulJobs.jobs) {
                Write-LogLine "  Jobs:"
                foreach ($job in $successfulJobs.jobs) {
                    Write-LogLine "    - $($job.name): $($job.conclusion)"
                }
            }
        }
        catch {
            Write-LogLine "  Jobs: unavailable"
            $successfulJobs = $null
        }

        $script:SummaryPayload.successful_run = [ordered]@{
            run = $successfulRun
            jobs = if ($successfulJobs) { $successfulJobs.jobs } else { @() }
        }
        Add-RunSummaryRows -Category "successful_run" -RunInfo $successfulRun -Jobs $successfulJobs
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

    $script:SummaryPayload.recent_failed_runs = @(
        $recentFailedRuns | ForEach-Object {
            [ordered]@{
                run_id = $_.databaseId
                workflow = $_.workflowName
                title = $_.displayTitle
                branch = $_.headBranch
                status = $_.status
                conclusion = $_.conclusion
                created_at = $_.createdAt
                updated_at = $_.updatedAt
            }
        }
    )

    Write-LogLine ""
    Write-LogLine "Inspecting failed run: $($failedRun.databaseId)"
    $failedSummary = Invoke-GhText run view $failedRun.databaseId -R $Repo
    $failedSummary | ForEach-Object { Write-LogLine $_ }

    try {
        $failedJobs = Invoke-GhJson run view $failedRun.databaseId -R $Repo --json jobs
        if ($failedJobs.jobs) {
            Write-LogLine "  Jobs:"
            foreach ($job in $failedJobs.jobs) {
                Write-LogLine "    - $($job.name): $($job.conclusion)"
            }
        }
    }
    catch {
        Write-LogLine "  Jobs: unavailable"
        $failedJobs = $null
    }

    $script:SummaryPayload.latest_failed_run = [ordered]@{
        run = $failedRun
        jobs = if ($failedJobs) { $failedJobs.jobs } else { @() }
    }
    Add-RunSummaryRows -Category "latest_failed_run" -RunInfo $failedRun -Jobs $failedJobs

    Write-LogLine ""
    Write-LogLine "Downloading failed run log output"
    try {
        $failedLog = Invoke-GhText run view $failedRun.databaseId -R $Repo --log-failed
        $failedLog | ForEach-Object { Write-LogLine $_ }
    }
    catch {
        Write-LogLine "Failed log output unavailable."
        Write-LogLine $_.Exception.Message
    }

    Save-LogBuffer
}
catch {
    Write-LogLine ""
    Write-LogLine "GitHub CLI request failed."
    Write-LogLine $_.Exception.Message
    Save-LogBuffer
    exit 1
}
