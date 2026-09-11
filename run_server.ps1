# run_server.ps1 -- start the trend scanner service so it survives closed
# terminals AND closed Claude sessions, with NO console window.
#
# Why pythonw + WMI: Start-Process leaves the child inside the caller's job
# object and the assistant's tool session kills that job on exit; cmd.exe
# (the old launcher) flashed an empty black window on the owner's screen
# every time -- 2026-09-06. pythonw.exe has no console at all, and the
# server writes its own log because of that.
#
# Logs: logs\server.log
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (-not (Test-Path logs)) { New-Item -ItemType Directory logs | Out-Null }
if (Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "server already listening on :5001"
    exit 0
}
# right after a kill the port can still be held for a few seconds; a launch then dies silently
$waited = 0
while ((Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue) -and $waited -lt 20) {
    Start-Sleep -Seconds 1; $waited += 1
}
$pyw = Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = (Get-Command python).Source }
$cmd = '"' + $pyw + '" server.py --log logs\server.log'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
        -Arguments @{ CommandLine = $cmd; CurrentDirectory = $here }
if ($r.ReturnValue -ne 0) {
  Write-Error "could not start the server (WMI code $($r.ReturnValue))"
  exit 1
}
Start-Sleep -Seconds 3
Write-Host "server started (pid $($r.ProcessId)): http://localhost:5001/"
