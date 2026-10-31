[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$destination = Join-Path $projectRoot 'service\MinecraftDiscordBot.exe'
$temporary = $destination + '.download'
$expected = '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da'
$url = 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe'
if (Test-Path -LiteralPath $destination) {
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected) {
        Write-Host 'WinSW 2.12.0 ja verificado.'
        return
    }
    throw 'Executavel existente diverge do hash esperado. Revise antes de substituir.'
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temporary
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'Download recusado: SHA-256 diferente do esperado.'
    }
    Move-Item -LiteralPath $temporary -Destination $destination
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Host 'WinSW 2.12.0 x64 baixado e verificado.'
