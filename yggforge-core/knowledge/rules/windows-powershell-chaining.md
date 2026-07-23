---
id: 20260722222439-kr$$$$-p51$$$$$-sfak
title: PowerShell 5.1 不支持 && 分隔符
title_refined: PowerShell 5.1 用 ; + if ($?) 替代 && 链式执行
type: rule
status: active
confidence: medium
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-22
last_reviewed: 2026-07-22
tags:
  - powershell
  - windows
  - shell
  - command-chaining
  - compatibility
promoted_to: rule
when_to_read:
  - 在 Windows PowerShell 5.1 下编写或执行多步命令链时
---
# PowerShell 5.1 不支持 && 分隔符

## Rule

- Windows PowerShell 5.1 **不支持** `&&` / `||` 作为命令链分隔符（`&&` 是 PowerShell 7+ / pwsh / bash 才原生支持）。
- 在 5.1 下实现「前一条成功才执行下一条」的语义，用 `cmd1; if ($?) { cmd2 }`。
- 含 `$` 的参数（如 `$?`、`$env:VAR`）必须用**单引号**包裹传给外部程序，否则 PowerShell 会先做变量插值，导致传参失真。
- 若本机已安装 PowerShell 7（`pwsh`），可直接用 `&&`，无需绕写。

## Applies To

- 在 Windows 自带的 Windows PowerShell 5.1 环境下执行多步命令链
- `scope: cross-project`，本机 Windows 环境通用

## Not For

- PowerShell 7+（`pwsh`）、Linux/macOS 的 bash/zsh（原生支持 `&&`）
