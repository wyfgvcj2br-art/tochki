# This script mutates only a disposable Windows CI machine.
[CmdletBinding()]
param([switch]$CI, [switch]$EnvironmentOnly)
$ErrorActionPreference = 'Stop'
if (-not $env:GITHUB_ACTIONS -and -not $CI) { throw 'Run on a disposable Windows test machine with -CI.' }
$root = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $root 'VERSION') -Raw).Trim()
$setup = Join-Path $root "dist/Tochki-$version-Setup-x64.exe"
$evidence = Join-Path $root '.cache/validation'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$installFolder = Join-Path $env:ProgramFiles 'Tochki'
$uninstallKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{CB821F4C-9D80-4F96-9C9F-75F389817D98}_is1'
$shortcut = [IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Точки/Точки.lnk'))
$python = (Get-Command python).Source
$userName = 'ТочкиТест'
$plainPassword = 'Tt!' + [guid]::NewGuid().ToString('N') + 'Aa9'
$credential = [pscredential]::new(".\$userName",(ConvertTo-SecureString $plainPassword -AsPlainText -Force))
$firewallRules = @()
function Invoke-Setup([string]$File, [string]$Label, [string[]]$Extra=@()) {
    $log = Join-Path $evidence "$Label.log"
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',"/LOG=`"$log`"") + $Extra
    $process = Start-Process -FilePath $File -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "$Label failed: $($process.ExitCode)" }
}
function Invoke-User([string]$Phase, [string]$Label) {
    Write-Output "Testing standard user phase: $Label"
    $job = Join-Path $evidence "$Label-job.json"
    $result = Join-Path $evidence "$Label-result.json"
    @{
        phase=$Phase; python=$python; installFolder=$installFolder; shortcut=$shortcut
        smokeScript=(Join-Path $PSScriptRoot 'smoke_portable.py')
        verifyScript=(Join-Path $PSScriptRoot 'verify_user_data.py')
        environmentScript=(Join-Path $PSScriptRoot 'check_user_environment.py')
        result=$result
    } | ConvertTo-Json | Set-Content -LiteralPath $job -Encoding utf8
    $runner = Join-Path $PSScriptRoot 'run_installer_user.ps1'
    $powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $process = Start-Process -FilePath $powershell -WindowStyle Hidden -Credential $credential -LoadUserProfile -WorkingDirectory $evidence -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$runner`"","`"$job`"") -RedirectStandardOutput (Join-Path $evidence "$Label-stdout.log") -RedirectStandardError (Join-Path $evidence "$Label-stderr.log") -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $result)) {
        Get-Content -LiteralPath (Join-Path $evidence "$Label-stdout.log") -ErrorAction SilentlyContinue | Write-Output
        Get-Content -LiteralPath (Join-Path $evidence "$Label-stderr.log") -ErrorAction SilentlyContinue | Write-Output
        Get-ChildItem -LiteralPath $evidence -Filter '*-diagnostic-*' | ForEach-Object { Get-Content -LiteralPath $_.FullName -ErrorAction SilentlyContinue | Write-Output }
        throw "Standard user test failed: $Label; inspect validation logs."
    }
    $status = Get-Content -LiteralPath $result -Raw | ConvertFrom-Json
    if (-not $status.success) { throw "Standard user test failed: $($status.error)" }
}
try {
    if (Test-Path -LiteralPath $installFolder) { throw 'A clean Program Files/Tochki destination is required.' }
    if (Get-LocalUser -Name $userName -ErrorAction SilentlyContinue) { throw 'CI user already exists.' }
    New-LocalUser -Name $userName -Password $credential.Password -AccountNeverExpires | Out-Null
    $usersGroup = (Get-LocalGroup -SID 'S-1-5-32-545').Name
    Add-LocalGroupMember -Group $usersGroup -Member $userName
    & icacls.exe $evidence /grant '*S-1-5-32-545:(OI)(CI)(M)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not grant access to validation evidence.' }
    if ($EnvironmentOnly) {
        Invoke-User 'environment' 'standard-user-environment'
        return
    }
    # Synthetic prior installed version exercises a genuine Inno version transition.
    $baselineDir = Join-Path $evidence 'baseline'
    New-Item -ItemType Directory -Path $baselineDir -Force | Out-Null
    $compiler = Join-Path $root '.cache/tools/inno-7.1.1/ISCC.exe'
    $payload = Join-Path $root 'dist/installed/Точки'
    & $compiler '/DAppVersion=2.5.99' '/DBaselineTest=1' "/DPayload=$payload" "/DOutputPath=$baselineDir" (Join-Path $root 'installer/Tochki.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Baseline installer compilation failed.' }
    Invoke-Setup (Join-Path $baselineDir 'Tochki-Setup-x64.exe') 'clean-install' @('/TASKS=desktopicon')
    if (-not (Test-Path -LiteralPath $shortcut)) { throw 'Start menu shortcut missing.' }
    if ((Get-Item -LiteralPath $shortcut).Length -eq 0) { throw 'Empty Start menu shortcut.' }
    # Resolve and launch the .lnk through Windows Shell under the standard user.
    # WScript.Shell may expose an empty TargetPath for a shell-ID-list link.
    if ((Get-ItemProperty -LiteralPath $uninstallKey).DisplayVersion -ne '2.5.99') { throw 'Baseline uninstall registration missing.' }
    $runtime = @(Get-ChildItem -LiteralPath (Join-Path $installFolder 'WebView2') -Filter msedgewebview2.exe -Recurse)
    if ($runtime.Count -ne 1) { throw 'Wrong fixed runtime payload.' }
    foreach ($program in @((Join-Path $installFolder 'Точки.exe'),$runtime[0].FullName)) {
        $rule = 'Tochki CI offline '+[guid]::NewGuid().ToString()
        New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program $program -Action Block | Out-Null
        $firewallRules += $rule
    }
    Invoke-User 'fresh' 'standard-user-initial'
    Invoke-Setup $setup 'upgrade'
    if ((Get-ItemProperty -LiteralPath $uninstallKey).DisplayVersion -ne $version) { throw 'Upgrade registration version is wrong.' }
    $info = (Get-Item -LiteralPath (Join-Path $installFolder 'Точки.exe')).VersionInfo
    if ($info.ProductVersion -ne $version -or $info.CompanyName -ne 'Saudade_meow') { throw 'Wrong EXE product metadata.' }
    Invoke-User 'reuse' 'standard-user-upgraded'
    Invoke-Setup (Join-Path $installFolder 'unins000.exe') 'uninstall'
    if (Test-Path -LiteralPath $uninstallKey) { throw 'Uninstall registration remains.' }
    if (Test-Path -LiteralPath $shortcut) { throw 'Start menu shortcut remains.' }
    Invoke-User 'preserved' 'data-after-uninstall'
    Invoke-Setup $setup 'reinstall' @('/TASKS=desktopicon')
    Invoke-User 'reuse' 'standard-user-reinstalled'
    Invoke-Setup (Join-Path $installFolder 'unins000.exe') 'final-uninstall'
    Invoke-User 'preserved' 'data-after-final-uninstall'
    @{ success=$true; version=$version; account=$userName
       cleanInstall=$true; standardUser=$true; offlineFirewall=$true
       startMenu=$true; upgradeBaseline='synthetic 2.5.99, same payload'
       upgrade=$true; uninstall=$true; reinstall=$true; userDataPreserved=$true
       hostPython='test harness only; app launched with Windows-only PATH'
       manualNotTested=@('Windows 10','clean OS without Python installation','interactive installer pages','native migration confirmation and folder dialogs','actual Windows DPI 100/125/150/200')
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'installation-results.json') -Encoding utf8
} finally {
    foreach ($rule in $firewallRules) { Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue }
    if (Get-LocalUser -Name $userName -ErrorAction SilentlyContinue) { Remove-LocalUser -Name $userName -ErrorAction SilentlyContinue }
}
