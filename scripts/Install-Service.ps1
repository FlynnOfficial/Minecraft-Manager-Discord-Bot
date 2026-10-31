#Requires -RunAsAdministrator
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$wrapper = Join-Path $projectRoot 'service\MinecraftDiscordBot.exe'
if (Get-Service -Name MinecraftDiscordBot -ErrorAction SilentlyContinue) {
    throw 'Servico ja instalado. Use os scripts de controle ou desinstale antes de reinstalar.'
}
if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Execute Setup.ps1 primeiro.' }
Set-Location -LiteralPath $projectRoot
& $venvPython -m minecraft_bot check
if ($LASTEXITCODE -ne 0) { throw 'Corrija a configuracao antes de instalar o servico.' }
& $venvPython -c "from minecraft_bot.config import Config,ROOT; c=Config.load(); assert c.data_dir == ROOT / 'data' and c.log_dir == ROOT / 'logs', 'Use data/logs locais ao instalar o servico'"
if ($LASTEXITCODE -ne 0) { throw 'O instalador exige DATA_DIR=data e LOG_DIR=logs para aplicar ACLs.' }
& (Join-Path $PSScriptRoot 'Get-WinSW.ps1')
$template = Get-Content -LiteralPath (Join-Path $projectRoot 'service\MinecraftDiscordBot.xml.template') -Raw
$xmlRoot = [Security.SecurityElement]::Escape($projectRoot)
$xmlPython = [Security.SecurityElement]::Escape($venvPython)
$rendered = $template.Replace('__ROOT__', $xmlRoot).Replace('__PYTHON__', $xmlPython)
[xml]$validatedXml = $rendered
$xmlPath = Join-Path $projectRoot 'service\MinecraftDiscordBot.xml'
[IO.File]::WriteAllText($xmlPath, $validatedXml.OuterXml, (New-Object Text.UTF8Encoding($false)))

# Dedicated deployment folder only. LocalService reads code/config, writes data/logs.
# Replace root ACL; children inherit it, so a broad old explicit grant cannot expose .env.
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner($ownerSid)
$inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
$propagate = [Security.AccessControl.PropagationFlags]::None
$allow = [Security.AccessControl.AccessControlType]::Allow
foreach ($sid in @($ownerSid.Value, 'S-1-5-18', 'S-1-5-32-544')) {
    $identity = New-Object Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', $inherit, $propagate, $allow)
    $acl.AddAccessRule($rule)
}
$localService = New-Object Security.Principal.SecurityIdentifier('S-1-5-19')
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($localService, 'ReadAndExecute', $inherit, $propagate, $allow)))
# Reject reparse points before recursive ACL work can touch another location.
if (Get-ChildItem -LiteralPath $projectRoot -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
    throw 'A pasta contem links/reparse points. Use uma pasta de instalacao dedicada sem links.'
}
Set-Acl -LiteralPath $projectRoot -AclObject $acl
$children = Get-ChildItem -LiteralPath $projectRoot -Force
foreach ($child in $children) {
    & icacls.exe $child.FullName /reset /T /Q
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao aplicar ACL. Servico nao instalado.' }
}
foreach ($name in @('data', 'logs')) {
    $directory = Join-Path $projectRoot $name
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    & icacls.exe $directory /grant '*S-1-5-19:(OI)(CI)M' /Q
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao conceder acesso aos dados/logs.' }
}
& $wrapper install
if ($LASTEXITCODE -ne 0) { throw 'WinSW nao conseguiu instalar o servico.' }
Write-Host 'Servico instalado como LocalService (sem privilegios de administrador).'
Write-Host 'Execute Start-Service.ps1. Nenhuma configuracao do Crafty foi alterada.'
