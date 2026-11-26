param([Parameter(Mandatory=$true)][string]$JobFile)
$ErrorActionPreference = 'Stop'
$job = Get-Content -LiteralPath $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
try {
# Start-Process -Credential inherits the runner's environment. Rebuild it for
# the actual logon token, as an interactive Windows logon would do.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$profileKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\' + $identity.User.Value
$testProfile = [Environment]::ExpandEnvironmentVariables((Get-ItemProperty -LiteralPath $profileKey).ProfileImagePath)
$compilerTemp = Join-Path $testProfile 'Tochki-CI-Temp'
New-Item -ItemType Directory -Path $compilerTemp -Force | Out-Null
$env:TEMP = $compilerTemp
$env:TMP = $compilerTemp
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class TochkiUserEnvironment {
    [DllImport("userenv.dll", SetLastError=true)]
    private static extern bool CreateEnvironmentBlock(out IntPtr environment, IntPtr token, bool inherit);
    [DllImport("userenv.dll")]
    private static extern bool DestroyEnvironmentBlock(IntPtr environment);
    public static void Restore() {
        IntPtr environment;
        using (WindowsIdentity identity = WindowsIdentity.GetCurrent()) {
            if (!CreateEnvironmentBlock(out environment, identity.Token, false))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        }
        try {
            IntPtr cursor = environment;
            while (true) {
                string entry = Marshal.PtrToStringUni(cursor);
                if (String.IsNullOrEmpty(entry)) break;
                int separator = entry.IndexOf('=');
                if (separator > 0)
                    Environment.SetEnvironmentVariable(entry.Substring(0, separator), entry.Substring(separator+1), EnvironmentVariableTarget.Process);
                cursor = IntPtr.Add(cursor, (entry.Length+1)*2);
            }
        } finally { DestroyEnvironmentBlock(environment); }
    }
}
'@
[TochkiUserEnvironment]::Restore()
$env:PYTHONIOENCODING = 'utf-8'
if ($env:USERNAME -ne 'ТочкиТест') { throw 'Wrong standard-user environment.' }
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null

    if ($job.phase -eq 'preserved') {
        & $job.python $job.verifyScript $job.installFolder
    } else {
        $arguments = @($job.smokeScript, $job.installFolder, '--installed', '--standard-user', '--shortcut', $job.shortcut)
        if ($job.phase -eq 'reuse') { $arguments += '--reuse' }
        & $job.python @arguments
    }
    if ($LASTEXITCODE -ne 0) { throw "User smoke failed: $LASTEXITCODE" }
    @{ phase=$job.phase; user=[Security.Principal.WindowsIdentity]::GetCurrent().Name; success=$true } |
        ConvertTo-Json | Set-Content -LiteralPath $job.result -Encoding utf8
    exit 0
} catch {
    $_ | Out-String | Write-Output
    $localRoot = [Environment]::GetFolderPath('LocalApplicationData')
    $logs = if ($localRoot) { Join-Path $localRoot 'Tochki/Logs' } else { $null }
    $destination = Split-Path -Parent $job.result
    if ($logs -and (Test-Path -LiteralPath $logs)) {
        Get-ChildItem -LiteralPath $logs -File | ForEach-Object {
            $name = (Split-Path -Leaf $job.result) + '-diagnostic-' + $_.Name
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destination $name) -ErrorAction SilentlyContinue
        }
    }
    @{ phase=$job.phase; user=[Environment]::UserName; success=$false; error=$_.ToString() } |
        ConvertTo-Json | Set-Content -LiteralPath $job.result -Encoding utf8
    exit 1
}
