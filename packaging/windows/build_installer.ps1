Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..\..")
Set-Location $projectRoot

function Resolve-Python {
    $candidates = @(@(
        (Join-Path $projectRoot ".venv\Scripts\python.exe"),
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    ) | Where-Object { $_ -and (Test-Path $_) })

    if ($candidates.Count -gt 0) {
        return $candidates[0]
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python not found. Install Python or create .venv before building."
}

function Resolve-Iscc {
    $candidates = @(@(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path $_) })

    if ($candidates.Count -gt 0) {
        return $candidates[0]
    }

    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($iscc) {
        return $iscc.Source
    }

    throw "Inno Setup (ISCC.exe) not found. Install Inno Setup 6 to build the installer."
}

$pythonExe = Resolve-Python
$isccExe = Resolve-Iscc
$specPath = Join-Path $scriptDir "LegalDesk.spec"
$issPath = Join-Path $scriptDir "LegalDesk.iss"

$versionLine = Select-String -Path (Join-Path $projectRoot "backend\main.py") -Pattern 'APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $versionLine) {
    throw "APP_VERSION not found in backend/main.py"
}
$version = $versionLine.Matches[0].Groups[1].Value

Write-Host "Using Python: $pythonExe"
Write-Host "Using Inno Setup: $isccExe"
Write-Host "Building LegalDesk version $version"

Remove-Item -Path (Join-Path $projectRoot "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $projectRoot "dist") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $projectRoot "dist-installer") -Recurse -Force -ErrorAction SilentlyContinue

& $pythonExe -m PyInstaller --noconfirm $specPath
& $isccExe "/DMyAppVersion=$version" $issPath

Write-Host "Installer created in dist-installer"
