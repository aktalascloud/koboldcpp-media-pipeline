param([switch]$SkipModelDownloads,[string]$GPENPath)
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskManifest=Get-Content -LiteralPath (Join-Path $taskRoot 'release-assets.json') -Raw | ConvertFrom-Json
foreach ($taskAsset in $taskManifest.assets) {
    if ([IO.Path]::GetFileName($taskAsset.name) -ne $taskAsset.name) { throw 'Invalid release asset name' }
    $taskArchive=Join-Path $taskRoot $taskAsset.name
    if (-not (Test-Path -LiteralPath $taskArchive)) { Invoke-WebRequest -Uri $taskAsset.url -OutFile $taskArchive }
    if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskAsset.sha256) { throw ('Asset SHA256 mismatch: '+$taskAsset.name) }
    Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskRoot -Force
    Remove-Item -LiteralPath $taskArchive
}
if ($GPENPath) {
    $taskDestination=Join-Path $taskRoot 'tools\detailer_models\gpen_bfr_512.onnx'
    New-Item -ItemType Directory -Path (Split-Path -Parent $taskDestination) -Force | Out-Null
    Copy-Item -LiteralPath (Resolve-Path -LiteralPath $GPENPath).Path -Destination $taskDestination
}
$taskArguments=@('-I','-B',(Join-Path $taskRoot 'tools\Setup.py'))
if ($SkipModelDownloads) { $taskArguments+='--skip-model-downloads' }
& (Join-Path $taskRoot 'runtime\python\python.exe') @taskArguments
exit $LASTEXITCODE
