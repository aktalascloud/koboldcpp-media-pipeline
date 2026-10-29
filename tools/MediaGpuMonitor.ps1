param([Parameter(Mandatory=$true)][string]$OutputPath,[Parameter(Mandatory=$true)][int]$TargetPid)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))+'\'
$target=[IO.Path]::GetFullPath($OutputPath)
if(-not ($target.StartsWith($root+'OUTPUTS\video\',[StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($root+'RESULTS\Video\',[StringComparison]::OrdinalIgnoreCase))){throw 'Unexpected media monitor destination'}
$encoding=[Text.UTF8Encoding]::new($false)
$failures=0
for($sample=0;$sample -lt 900;$sample++){
    # WDDM removes old process instances while switching Native/DirectML.
    # An unrelated stale instance must not discard valid current-process data.
    $set=Get-Counter '\GPU Process Memory(*)\Dedicated Usage','\GPU Process Memory(*)\Shared Usage' -MaxSamples 1 -ErrorAction SilentlyContinue
    if(-not $set -or -not $set.CounterSamples){
        $failures++
        [IO.File]::AppendAllText($target,(@{time=[DateTime]::UtcNow.ToString('o');pid=$TargetPid;dedicated=0;shared=0;valid=$false;consecutive_failures=$failures}|ConvertTo-Json -Compress)+"`n",$encoding)
        if($failures -ge 10){throw 'GPU memory counters unavailable for10 consecutive samples'}
        Start-Sleep -Milliseconds 750
        continue
    }
    $failures=0
    $dedicated=0L;$shared=0L
    foreach($counter in $set.CounterSamples){
        if($counter.InstanceName -notlike ('pid_'+$TargetPid+'_*')){continue}
        if($counter.Status -ne 0){continue}
        if($counter.Path.EndsWith('\dedicated usage')){$dedicated+=[long]$counter.CookedValue}
        if($counter.Path.EndsWith('\shared usage')){$shared+=[long]$counter.CookedValue}
    }
    [IO.File]::AppendAllText($target,(@{time=$set.Timestamp.ToUniversalTime().ToString('o');pid=$TargetPid;dedicated=$dedicated;shared=$shared;valid=$true}|ConvertTo-Json -Compress)+"`n",$encoding)
    Start-Sleep -Milliseconds 750
}
