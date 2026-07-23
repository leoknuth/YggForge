[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 兼容双风格：
# 1) 新：ygg 子命令风格（推荐）—— deploy.ps1 link cursor / deploy.ps1 status cursor
# 2) 旧：deploy.py 旗标风格 —— --action deploy --mode link --targets cursor
# 旧风格仍直调 deploy.py（带 -X utf8）；新风格转发到 ygg。

function Find-Python {
    foreach ($candidate in @("python", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $candidate }
    }
    throw "Python is required. Install Python 3 and ensure 'python' or 'py' is available in PATH."
}

$legacy = $false
foreach ($a in $Args) {
    if ($a -match '^--(action|mode|targets|preview)') { $legacy = $true; break }
}

if ($legacy) {
    $python = Find-Python
    & $python -X utf8 (Join-Path $ScriptDir "cmds/ops/deploy.py") @Args
    exit $LASTEXITCODE
}

$first = if ($Args.Count -gt 0) { $Args[0] } else { "" }
if ($first -in @("status", "import")) {
    $rest = @()
    if ($Args.Count -gt 1) { $rest = $Args[1..($Args.Count - 1)] }
    & (Join-Path $ScriptDir "ygg.ps1") $first @rest
    exit $LASTEXITCODE
}

& (Join-Path $ScriptDir "ygg.ps1") deploy @Args
exit $LASTEXITCODE
