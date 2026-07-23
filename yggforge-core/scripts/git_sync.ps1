[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 兼容双风格：
# 1) 新：ygg sync / 本脚本无参或 target → ygg sync；含 push → ygg push
# 2) 旧：git_sync.py 旗标 —— --action update|update-push

function Find-Python {
    foreach ($candidate in @("python", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $candidate }
    }
    throw "Python is required. Install Python 3 and ensure 'python' or 'py' is available in PATH."
}

$legacy = $false
foreach ($a in $Args) {
    if ($a -match '^--(action|repo|remote|branch)') { $legacy = $true; break }
}

if ($legacy) {
    $python = Find-Python
    & $python -X utf8 (Join-Path $ScriptDir "cmds/ops/git_sync.py") @Args
    exit $LASTEXITCODE
}

$joined = ($Args -join " ").ToLowerInvariant()
if ($joined -match '\bpush\b' -or $joined -match 'update-push') {
    & (Join-Path $ScriptDir "ygg.ps1") push @Args
    exit $LASTEXITCODE
}

& (Join-Path $ScriptDir "ygg.ps1") sync @Args
exit $LASTEXITCODE
