$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)

    $map = @{}
    if (-not (Test-Path $Path)) {
        return $map
    }

    Get-Content -Path $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $map[$parts[0].Trim()] = $parts[1].Trim()
        }
    }

    return $map
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$envFile = Join-Path $repoRoot ".env"
$templateFile = Join-Path $repoRoot "infra\secrets-template.env"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $envFile)) {
    Copy-Item -Path $templateFile -Destination $envFile -Force
    Write-Host "Created .env from template"
}

$cfg = Read-DotEnv -Path $envFile
$pythonExe = $cfg["PYTHON_EXE"]
if (-not $pythonExe) {
    $pythonExe = "python"
}

if (-not (Test-Path $pythonExe) -and $pythonExe -ne "python") {
    throw "Python executable not found: $pythonExe"
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment with: $pythonExe"
    & $pythonExe -m venv (Join-Path $repoRoot ".venv")
}

Write-Host "Installing dependencies"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed with code $LASTEXITCODE" }
& $venvPython -m pip install -r (Join-Path $repoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed with code $LASTEXITCODE" }

Write-Host "Running DB healthcheck + seed"
& $venvPython (Join-Path $repoRoot "scripts\seed_demo_data.py")
if ($LASTEXITCODE -ne 0) { throw "seed_demo_data.py failed with code $LASTEXITCODE" }

Write-Host "Bootstrap completed successfully"
