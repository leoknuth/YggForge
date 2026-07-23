[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "ygg.py"

$pythonCandidates = @("python", "py")
$pythonCommand = $null

foreach ($candidate in $pythonCandidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $pythonCommand = $candidate
        break
    }
}

if (-not $pythonCommand) {
    throw "Python is required. Install Python 3 and ensure 'python' or 'py' is available in PATH."
}

& $pythonCommand -X utf8 $PythonScript @Args
$exitCode = $LASTEXITCODE
exit $exitCode
