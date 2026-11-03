# Run on the Windows machine hosting Spark. No public listener is opened.
param([string]$SshHostAlias='fengz',[int]$Port=18091)
$ErrorActionPreference='Stop'
Write-Host "Keep this window running while PD uses the Windows local model."
while ($true) {
    & ssh.exe -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R "127.0.0.1:${Port}:127.0.0.1:${Port}" $SshHostAlias
    Write-Warning 'PD model tunnel ended; retrying in 5 seconds. Ctrl+C stops it.'
    Start-Sleep -Seconds 5
}
