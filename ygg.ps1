# Thin wrapper: forward to the deployable core CLI.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "yggforge-core\scripts\ygg.ps1") @args
exit $LASTEXITCODE
