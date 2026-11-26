param([Parameter(Mandatory=$true)][string]$JobFile)
$ErrorActionPreference = 'Stop'
$job = Get-Content -LiteralPath $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
try {
    if ($job.phase -eq 'preserved') {
        & $job.python $job.verifyScript $job.installFolder
    } else {
        $arguments = @($job.smokeScript, $job.installFolder, '--installed', '--standard-user', '--shortcut', $job.shortcut)
        if ($job.phase -eq 'reuse') { $arguments += '--reuse' }
        & $job.python @arguments
    }
    if ($LASTEXITCODE -ne 0) { throw "User smoke failed: $LASTEXITCODE" }
    @{ phase=$job.phase; user=[Environment]::UserName; success=$true } |
        ConvertTo-Json | Set-Content -LiteralPath $job.result -Encoding utf8
    exit 0
} catch {
    $_ | Out-String | Write-Output
    @{ phase=$job.phase; user=[Environment]::UserName; success=$false; error=$_.ToString() } |
        ConvertTo-Json | Set-Content -LiteralPath $job.result -Encoding utf8
    exit 1
}
