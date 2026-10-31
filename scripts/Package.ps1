$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$destination = Join-Path $projectRoot 'dist'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$zipPath = Join-Path $destination 'Minecraft-Discord-Crafty.zip'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath }
$archive = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
try {
    # Explicit allowlist: never package .env, tokens, certificates, state, logs or binaries.
    $files = @('.env.example', '.gitignore', 'pyproject.toml', 'requirements.txt',
               'requirements-dev.txt', 'README.md', 'LICENSE')
    foreach ($directory in @('minecraft_bot','tests','docs','scripts','service','certs')) {
        $base = Join-Path $projectRoot $directory
        $files += Get-ChildItem -LiteralPath $base -File -Recurse -Force |
            Where-Object { $_.Extension -notin @('.pyc','.exe','.xml') -and
                          $_.FullName -notmatch '__pycache__' -and
                          ($directory -ne 'certs' -or $_.Name -eq '.gitkeep') } |
            ForEach-Object { $_.FullName.Substring($projectRoot.Length + 1) }
    }
    foreach ($file in $files) {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, (Join-Path $projectRoot $file), $file.Replace('\','/'),
            [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $archive.Dispose() }
Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
