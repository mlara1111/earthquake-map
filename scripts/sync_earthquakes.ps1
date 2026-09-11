### Synchronize recent earthquake data through the Django management command.
### This wrapper is intended for Windows Task Scheduler and deliberately contains
### no earthquake business logic. All synchronization logic remains in Django.

[CmdletBinding()]
param(
    ### Number of days to synchronize backwards from the current time.
    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 3650)]
    [int]$LookbackDays = 90,

    ### Optional explicit synchronization start date.
    [Parameter(Mandatory = $false)]
    [datetime]$StartDate,

    ### Optional explicit synchronization end date.
    [Parameter(Mandatory = $false)]
    [datetime]$EndDate
)


### Resolve the repository root from the location of this script.
$ProjectRoot = Split-Path -Parent $PSScriptRoot

### Move into the repository so Docker Compose uses the correct compose.yaml.
Set-Location $ProjectRoot


### Verify that Docker is available before attempting the synchronization.
try {
    docker version | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Docker is not available."
    }
}
catch {
    Write-Error "Docker Desktop is not available or cannot be reached."
    exit 1
}


### Build the Django management command arguments.
$CommandArguments = @(
    "compose"
    "exec"
    "-T"
    "web"
    "python"
    "-u"
    "manage.py"
    "sync_earthquakes"
)


### Use explicit dates when the caller supplied them.
if ($PSBoundParameters.ContainsKey("StartDate")) {
    $CommandArguments += "--start-date"
    $CommandArguments += $StartDate.ToString("yyyy-MM-dd")
}

if ($PSBoundParameters.ContainsKey("EndDate")) {
    $CommandArguments += "--end-date"
    $CommandArguments += $EndDate.ToString("yyyy-MM-dd")
}


### Use the lookback period only when an explicit start date was not supplied.
if (-not $PSBoundParameters.ContainsKey("StartDate")) {
    $CommandArguments += "--lookback-days"
    $CommandArguments += $LookbackDays
}


$StartTimestamp = Get-Date

Write-Host "Starting earthquake synchronization..."
Write-Host "Project: $ProjectRoot"
Write-Host "Started: $StartTimestamp"
Write-Host ""


### Execute the existing Django synchronization command.
### The wrapper does not interpret or modify its output.
& docker @CommandArguments

$ExitCode = $LASTEXITCODE

$EndTimestamp = Get-Date
$Duration = $EndTimestamp - $StartTimestamp

Write-Host ""
Write-Host "Finished: $EndTimestamp"
Write-Host "Duration: $($Duration.ToString())"


### Propagate Django's exit code to the calling scheduler.
### Exit code 0 means success; any non-zero value means failure.
if ($ExitCode -eq 0) {
    Write-Host "Synchronization completed successfully."
}
else {
    Write-Error "Synchronization failed with exit code $ExitCode."
}

exit $ExitCode