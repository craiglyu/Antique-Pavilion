$ErrorActionPreference = 'Stop'

$apPreviewUrl = 'http://127.0.0.1:8765/scripts/GAS/review_desk/Index.html'
$apRepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$apBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

function Test-ApPreview {
    try {
        $apProbe = Invoke-WebRequest -Uri $apPreviewUrl -UseBasicParsing -TimeoutSec 1
        return $apProbe.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-ApPreview)) {
    $apPython = $null
    if (Test-Path -LiteralPath $apBundledPython) {
        $apPython = $apBundledPython
    }
    else {
        $apPythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($apPythonCommand) {
            $apPython = $apPythonCommand.Source
        }
    }

    if (-not $apPython) {
        throw '找不到 Python，無法啟動本地 Review Desk 預覽服務。'
    }

    Start-Process `
        -FilePath $apPython `
        -ArgumentList @('-m', 'http.server', '8765', '--bind', '127.0.0.1') `
        -WorkingDirectory $apRepoRoot `
        -WindowStyle Hidden | Out-Null

    $apReady = $false
    foreach ($apAttempt in 1..20) {
        Start-Sleep -Milliseconds 250
        if (Test-ApPreview) {
            $apReady = $true
            break
        }
    }
    if (-not $apReady) {
        throw 'Review Desk 預覽服務啟動逾時。'
    }
}

$apChromeCandidates = @(
    (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if ($apChromeCandidates.Count -gt 0) {
    Start-Process -FilePath $apChromeCandidates[0] -ArgumentList $apPreviewUrl
}
else {
    Start-Process $apPreviewUrl
}
