param([switch]$SkipModelDownloads,[string]$MossSourceDirectory,[string]$GPENPath,[string]$ListenHost='127.0.0.1')
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$taskManifest=Get-Content -LiteralPath (Join-Path $taskRoot 'release-assets.json') -Raw|ConvertFrom-Json
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Assert-TaskNoReparse([string]$Path){
    $taskParent=[IO.Path]::GetDirectoryName($Path)
    while($taskParent -and $taskParent.StartsWith($taskRoot,[StringComparison]::OrdinalIgnoreCase)){
        if((Test-Path -LiteralPath $taskParent) -and ((Get-Item -LiteralPath $taskParent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Reparse-point installation paths are not supported'}
        if($taskParent -eq $taskRoot){break}
        $taskParent=[IO.Path]::GetDirectoryName($taskParent)
    }
}
foreach($taskAsset in $taskManifest.assets){
    if([IO.Path]::GetFileName($taskAsset.name) -ne $taskAsset.name){throw 'Invalid release asset name'}
    $taskArchive=Join-Path $taskRoot $taskAsset.name
    if(-not(Test-Path -LiteralPath $taskArchive)){Invoke-WebRequest -Uri $taskAsset.url -OutFile $taskArchive}
    if((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskAsset.sha256){throw ('Asset SHA256 mismatch: '+$taskAsset.name)}
    $taskZip=[IO.Compression.ZipFile]::OpenRead($taskArchive)
    try{
        foreach($taskEntry in $taskZip.Entries){
            $taskName=$taskEntry.FullName.Replace('\','/')
            if($taskName.StartsWith('/') -or $taskName.Split('/') -contains '..' -or $taskName.Contains(':')){throw 'Unsafe release archive path'}
            $taskAllowed=$false
            foreach($taskPrefix in $taskAsset.extract_prefixes){if(($taskPrefix.EndsWith('/') -and $taskName.StartsWith($taskPrefix,[StringComparison]::Ordinal)) -or $taskName -eq $taskPrefix){$taskAllowed=$true;break}}
            if(-not $taskAllowed -or $taskName.EndsWith('/')){continue}
            if($taskName.Split('/') -contains '__pycache__' -or $taskName.EndsWith('.pyc')){continue}
            $taskOutputName=$taskName
            if($taskAsset.name -eq 'koboldcpp-windows-haswell-vulkan.zip' -and $taskName -ne 'koboldcpp-nocuda.exe'){$taskOutputName='licenses/native-release/'+$taskName}
            elseif($taskName.StartsWith('licenses/')){$taskOutputName='licenses/base-assets/'+$taskAsset.name.Replace('.zip','')+'/'+$taskName.Substring(9)}
            $taskDestination=[IO.Path]::GetFullPath((Join-Path $taskRoot $taskOutputName.Replace('/','\')))
            if(-not $taskDestination.StartsWith($taskRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Archive escaped installation root'}
            Assert-TaskNoReparse $taskDestination
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($taskDestination))|Out-Null
            if(Test-Path -LiteralPath $taskDestination){
                $taskHasher=[Security.Cryptography.SHA256]::Create();$taskInput=$taskEntry.Open()
                try{$taskExpected=([BitConverter]::ToString($taskHasher.ComputeHash($taskInput))).Replace('-','').ToLowerInvariant()}finally{$taskInput.Dispose();$taskHasher.Dispose()}
                if((Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected){throw ('Existing asset differs and is preserved: '+$taskOutputName)}
                continue
            }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($taskEntry,$taskDestination,$false)
        }
    }finally{$taskZip.Dispose()}
    Remove-Item -LiteralPath $taskArchive
}
$taskArguments=@('-I','-B',(Join-Path $taskRoot 'tools\Setup.py'),'--listen-host',$ListenHost)
if($SkipModelDownloads){$taskArguments+='--skip-model-downloads'}
if($MossSourceDirectory){$taskArguments+=@('--moss-source-directory',(Resolve-Path -LiteralPath $MossSourceDirectory).Path)}
if($GPENPath){$taskArguments+=@('--gpen-path',(Resolve-Path -LiteralPath $GPENPath).Path)}
& (Join-Path $taskRoot 'runtime\python\python.exe') @taskArguments
exit $LASTEXITCODE
