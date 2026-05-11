$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$workspaceRoot = Split-Path -Parent $projectRoot
$logDir = Join-Path $projectRoot "output\\runtime_logs"
$feishuPidFile = Join-Path $logDir "feishu.pid"
$cloudPidFile = Join-Path $logDir "cloudflared.pid"
$cloudLogFile = Join-Path $logDir "cloudflared.log"
$cloudUrlFile = Join-Path $logDir "cloudflared.url.txt"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Get-DotEnvSettings {
    param([string]$EnvFile)

    $settings = @{
        FEISHU_PORT = "8001"
        FEISHU_PATH = "/feishu/webhook"
    }

    if (-not (Test-Path $EnvFile)) {
        return $settings
    }

    foreach ($rawLine in Get-Content -Path $EnvFile -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")

        if ($key -in @("FEISHU_PORT", "FEISHU_PATH")) {
            $settings[$key] = $value
        }
    }

    return $settings
}

function Get-RunningProcessFromPidFile {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return $null
    }

    $rawPid = (Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $pidValue = 0
    if (-not [int]::TryParse([string]$rawPid, [ref]$pidValue)) {
        return $null
    }

    try {
        return Get-Process -Id $pidValue -ErrorAction Stop
    } catch {
        return $null
    }
}

function Start-HiddenProcess {
    param(
        [string]$FilePath,
        [string]$Arguments,
        [string]$WorkingDirectory
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    return [System.Diagnostics.Process]::Start($psi)
}

function Stop-RunningProcess {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process) {
        return
    }

    try {
        Stop-Process -Id $Process.Id -Force -ErrorAction Stop
    } catch {
    }
}

function Test-FeishuReady {
    param(
        [int]$Port,
        [string]$Path
    )

    $url = "http://127.0.0.1:$Port$Path"

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3
        return [pscustomobject]@{
            Ready = ($response.StatusCode -eq 200)
            Url = $url
            Status = $response.StatusCode
        }
    } catch {
        return [pscustomobject]@{
            Ready = $false
            Url = $url
            Status = $_.Exception.Message
        }
    }
}

function Get-TryCloudflareUrl {
    param([string]$LogFile)

    if (-not (Test-Path $LogFile)) {
        return $null
    }

    return Select-String -Path $LogFile -Pattern 'https://[-0-9a-z]+\.trycloudflare\.com' -AllMatches |
        ForEach-Object { $_.Matches.Value } |
        Select-Object -Last 1
}

function Test-PublicWebhookReady {
    param([string]$Url)

    if (-not $Url) {
        return [pscustomobject]@{
            Ready = $false
            Status = "missing public webhook url"
        }
    }

    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(8)

    try {
        $response = $client.GetAsync($Url).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return [pscustomobject]@{
            Ready = $response.IsSuccessStatusCode
            Status = "$([int]$response.StatusCode) $body"
        }
    } catch {
        return [pscustomobject]@{
            Ready = $false
            Status = $_.Exception.Message
        }
    } finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

$settings = Get-DotEnvSettings -EnvFile (Join-Path $projectRoot ".env")
$feishuPort = [int]$settings.FEISHU_PORT
$feishuPath = $settings.FEISHU_PATH
if (-not $feishuPath.StartsWith("/")) {
    $feishuPath = "/$feishuPath"
}

$pythonPath = (Get-Command python -ErrorAction Stop).Source
$cloudflaredPath = (Get-Command cloudflared -ErrorAction Stop).Source

$feishuProbe = Test-FeishuReady -Port $feishuPort -Path $feishuPath
$feishuProc = Get-RunningProcessFromPidFile -PidFile $feishuPidFile
$startedFeishu = $false

if (-not $feishuProbe.Ready) {
    $feishuProc = Start-HiddenProcess -FilePath $pythonPath -Arguments "-m audit_multi_agent_rag.cli feishu" -WorkingDirectory $workspaceRoot
    Set-Content -Path $feishuPidFile -Value $feishuProc.Id -Encoding ASCII
    $startedFeishu = $true

    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $feishuProbe = Test-FeishuReady -Port $feishuPort -Path $feishuPath
        if ($feishuProbe.Ready) {
            break
        }
    }
}

if (-not $feishuProbe.Ready) {
    throw "Feishu server did not become ready on $($feishuProbe.Url). Last status: $($feishuProbe.Status)"
}

if (-not $feishuProc) {
    $feishuProc = Get-RunningProcessFromPidFile -PidFile $feishuPidFile
}

$cloudProc = Get-RunningProcessFromPidFile -PidFile $cloudPidFile
$cloudUrl = $null
$startedCloudflared = $false

if ($cloudProc) {
    $cloudUrl = Get-TryCloudflareUrl -LogFile $cloudLogFile
    if ($cloudUrl) {
        $existingPublicWebhookUrl = "$cloudUrl$feishuPath"
        $publicProbe = Test-PublicWebhookReady -Url $existingPublicWebhookUrl
        if (-not $publicProbe.Ready) {
            Stop-RunningProcess -Process $cloudProc
            Remove-Item -Path $cloudPidFile, $cloudLogFile, $cloudUrlFile -Force -ErrorAction SilentlyContinue
            $cloudProc = $null
            $cloudUrl = $null
        }
    } else {
        Stop-RunningProcess -Process $cloudProc
        Remove-Item -Path $cloudPidFile, $cloudLogFile, $cloudUrlFile -Force -ErrorAction SilentlyContinue
        $cloudProc = $null
    }
}

if (-not $cloudProc) {
    Remove-Item -Path $cloudLogFile, $cloudUrlFile -Force -ErrorAction SilentlyContinue
    $cloudArgs = "tunnel --url http://127.0.0.1:$feishuPort --no-autoupdate --logfile `"$cloudLogFile`""
    $cloudProc = Start-HiddenProcess -FilePath $cloudflaredPath -Arguments $cloudArgs -WorkingDirectory $workspaceRoot
    Set-Content -Path $cloudPidFile -Value $cloudProc.Id -Encoding ASCII
    $startedCloudflared = $true

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        $cloudUrl = Get-TryCloudflareUrl -LogFile $cloudLogFile
        if ($cloudUrl) {
            break
        }

        try {
            $null = Get-Process -Id $cloudProc.Id -ErrorAction Stop
        } catch {
            break
        }
    }
}

if ($cloudUrl) {
    Set-Content -Path $cloudUrlFile -Value $cloudUrl -Encoding ASCII
}

$publicWebhookUrl = $null
if ($cloudUrl) {
    $publicWebhookUrl = "$cloudUrl$feishuPath"
}

Write-Host ""
Write-Host ("Feishu server  : {0} (PID {1})" -f ($(if ($startedFeishu) { "started" } else { "ready" })), $(if ($feishuProc) { $feishuProc.Id } else { "unknown" }))
Write-Host ("Local webhook  : {0}" -f $feishuProbe.Url)
Write-Host ("Cloudflared    : {0} (PID {1})" -f ($(if ($startedCloudflared) { "started" } else { "ready" })), $(if ($cloudProc) { $cloudProc.Id } else { "unknown" }))

if ($publicWebhookUrl) {
    Write-Host ("Public webhook : {0}" -f $publicWebhookUrl)
} else {
    Write-Host ("Public webhook : pending, check {0}" -f $cloudLogFile)
}

Write-Host ("Runtime logs   : {0}" -f $logDir)
