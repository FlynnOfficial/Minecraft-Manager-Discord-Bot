[CmdletBinding()]
param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
if (-not $PythonExe) {
    $PythonExe = (& py -3.13 -c 'import sys; print(sys.executable)')
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.13 x64 e tente novamente.' }
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
& $PythonExe -c "import sys,struct; assert sys.version_info[:2] == (3,13) and struct.calcsize('P') == 8"
if ($LASTEXITCODE -ne 0) { throw 'Este projeto exige Python 3.13 x64.' }
& $PythonExe -m venv (Join-Path $projectRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente virtual.' }
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $venvPython -m pip install --require-hashes -r (Join-Path $projectRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias.' }
foreach ($directory in @('data', 'logs', 'certs')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $directory) | Out-Null
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
    Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination (Join-Path $projectRoot '.env')
}
Write-Host 'Ambiente pronto. Preencha .env e execute check e doctor conforme README.'
