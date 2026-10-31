$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $venvPython -m pip install --require-hashes -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias de teste.' }
& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Testes falharam.' }
& $venvPython -m ruff check minecraft_bot tests
if ($LASTEXITCODE -ne 0) { throw 'Verificacao estatica falhou.' }
& $venvPython -m compileall -q minecraft_bot
if ($LASTEXITCODE -ne 0) { throw 'Compilacao falhou.' }
