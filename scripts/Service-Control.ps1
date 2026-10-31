#Requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateSet('start','stop','restart','uninstall')][string]$Action)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$wrapper = Join-Path $projectRoot 'service\MinecraftDiscordBot.exe'
if (-not (Test-Path -LiteralPath $wrapper)) { throw 'WinSW nao encontrado.' }
$expected = '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da'
if ((Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'WinSW diverge do hash esperado.'
}
if ($Action -eq 'uninstall') {
    $service = Get-Service -Name MinecraftDiscordBot -ErrorAction Stop
    if ($service.Status -ne 'Stopped') {
        & $wrapper stop
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel parar o bot.' }
    }
}
& $wrapper $Action
if ($LASTEXITCODE -ne 0) { throw "Falha na operacao $Action do servico do bot." }
