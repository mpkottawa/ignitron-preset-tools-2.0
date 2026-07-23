$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppName = "Ignitron Preset Tools v2.0"
$Entry = Join-Path $Root "ignitron_preset_tools_v2.0.py"
$Icon = Join-Path $Root "IPT.ico"
$BuildRoot = Join-Path $Root "build"
$DistRoot = Join-Path $Root "release"
$DistApp = Join-Path $DistRoot $AppName
$ZipPath = Join-Path $DistRoot "$AppName.zip"

if (-not (Test-Path -LiteralPath $Entry)) {
  throw "Missing entry point: $Entry"
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot | Out-Null

$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
  throw "PyInstaller was not found. Install dependencies with: py -3 -m pip install -r requirements.txt"
}

$addData = @()
if (Test-Path -LiteralPath (Join-Path $Root "reference")) {
  $addData += "--add-data"
  $addData += "$(Join-Path $Root 'reference');reference"
}
if (Test-Path -LiteralPath (Join-Path $Root "data")) {
  $addData += "--add-data"
  $addData += "$(Join-Path $Root 'data');data"
}
if (Test-Path -LiteralPath (Join-Path $Root "Ignitron")) {
  $addData += "--add-data"
  $addData += "$(Join-Path $Root 'Ignitron');Ignitron"
}
if (Test-Path -LiteralPath $Icon) {
  $addData += "--add-data"
  $addData += "$Icon;."
}

$iconArgs = @()
if (Test-Path -LiteralPath $Icon) {
  $iconArgs += "--icon"
  $iconArgs += $Icon
}

& pyinstaller `
  --noconfirm `
  --windowed `
  --name $AppName `
  --distpath $DistRoot `
  --workpath (Join-Path $BuildRoot "pyinstaller") `
  --specpath $BuildRoot `
  @iconArgs `
  @addData `
  --add-data "$(Join-Path $Root 'preset_puller.py');." `
  --add-data "$(Join-Path $Root 'preset_chart.py');." `
  --add-data "$(Join-Path $Root 'preset_converter.py');." `
  $Entry

Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistApp "README.txt") -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistApp "README.md") -Force
Copy-Item -LiteralPath (Join-Path $Root "RELEASE_NOTES.md") -Destination (Join-Path $DistApp "RELEASE_NOTES.txt") -Force
Copy-Item -LiteralPath (Join-Path $Root "RELEASE_NOTES.md") -Destination (Join-Path $DistApp "RELEASE_NOTES.md") -Force

if (Test-Path -LiteralPath $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $DistApp "*") -DestinationPath $ZipPath

Write-Host "Built $AppName"
Write-Host "Folder: $DistApp"
Write-Host "Zip:    $ZipPath"
