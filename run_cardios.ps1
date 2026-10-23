<#
  Cardios - one-command launcher (Windows PowerShell)

  Starts the Flask backend and the Vite frontend, waits until the backend is
  really answering, then opens the app.

      powershell -ExecutionPolicy Bypass -File .\run_cardios.ps1

  It also repairs the most common blocker: a virtual environment that was
  created by another Windows user or in another folder. Windows venvs are not
  relocatable - Scripts\python.exe is a stub that reads pyvenv.cfg and launches
  the base interpreter recorded there, so if that path is gone you get
  "No Python at '...'" and nothing starts.
#>

$ErrorActionPreference = "Stop"
$Root         = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPort  = 49232
$FrontendPort = 5176
$VenvDir      = Join-Path $Root ".venv311"
$VenvPython   = Join-Path $VenvDir "Scripts\python.exe"
$VenvCfg      = Join-Path $VenvDir "pyvenv.cfg"

function Write-Step($msg)  { Write-Host "  [..] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "  [ok] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  Cardios - Cardiac Intelligence Workspace" -ForegroundColor Cyan
Write-Host "  Heart-Risk | ECG | Clinical Evidence" -ForegroundColor DarkGray
Write-Host ""

# --------------------------------------------------------------------------
# Is the venv's python actually runnable?
# --------------------------------------------------------------------------
function Test-PythonRuns([string]$exe) {
    if (-not (Test-Path $exe)) { return $false }
    try {
        $null = & $exe -c "import sys" 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

# Find a usable Python 3.11 on this machine.
function Find-BasePython311 {
    $candidates = @()
    try {
        $found = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { $candidates += $found.Trim() }
    } catch { }
    foreach ($name in @("python", "python3.11", "python3")) {
        try {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if ($cmd) {
                $ver = & $cmd.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
                if ($LASTEXITCODE -eq 0 -and $ver -and $ver.Trim() -eq "3.11") { $candidates += $cmd.Source }
            }
        } catch { }
    }
    if ($candidates.Count -gt 0) { return $candidates[0] }
    return $null
}

Write-Step "Checking the Python environment..."
$pythonOk = Test-PythonRuns $VenvPython

if (-not $pythonOk -and (Test-Path $VenvCfg)) {
    Write-Warn "The virtual environment is broken - it points at a Python that is not on this machine."
    $recorded = (Select-String -Path $VenvCfg -Pattern '^home\s*=\s*(.+)$').Matches.Groups[1].Value
    Write-Host "       recorded base: $recorded" -ForegroundColor DarkGray

    $base = Find-BasePython311
    if ($base) {
        $baseDir = Split-Path -Parent $base
        Write-Step "Found Python 3.11 at $base - repointing the environment at it"
        Copy-Item $VenvCfg "$VenvCfg.bak" -Force
        @(
            "home = $baseDir",
            "include-system-site-packages = false",
            "version = 3.11.9",
            "executable = $base"
        ) | Set-Content -Path $VenvCfg -Encoding ASCII
        $pythonOk = Test-PythonRuns $VenvPython
        if ($pythonOk) {
            Write-Ok "Environment repaired - the installed packages are reusable, no re-download needed."
        } else {
            Write-Warn "Repair did not take; the environment will need recreating."
            Copy-Item "$VenvCfg.bak" $VenvCfg -Force
        }
    } else {
        Write-Fail "No Python 3.11 found on this machine."
    }
}

if (-not $pythonOk) {
    Write-Host ""
    Write-Fail "The backend cannot start without a working Python environment."
    Write-Host ""
    Write-Host "  Fix it once, then re-run this script:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    1. Install Python 3.11 (tick 'Add Python to PATH'):"
    Write-Host "         https://www.python.org/downloads/release/python-3119/"
    Write-Host ""
    Write-Host "    2. Recreate the environment:"
    Write-Host "         cd `"$Root`""
    Write-Host "         Remove-Item -Recurse -Force .venv311"
    Write-Host "         py -3.11 -m venv .venv311"
    Write-Host "         .\.venv311\Scripts\python.exe -m pip install --upgrade pip"
    Write-Host "         .\.venv311\Scripts\python.exe -m pip install -r requirements.txt"
    Write-Host ""
    Write-Host "  (Step 2 downloads TensorFlow, ~500 MB - allow several minutes.)" -ForegroundColor DarkGray
    Write-Host ""
    exit 1
}
Write-Ok "Python environment usable"

# --------------------------------------------------------------------------
# Other preflight
# --------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Root "node_modules"))) {
    Write-Fail "node_modules missing. Run:  npm install"
    exit 1
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Warn "No .env - copying .env.example"
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
}
if (Test-Path (Join-Path $Root "backend\rag\corpus\corpus.db")) {
    Write-Ok "Guideline corpus present"
} else {
    Write-Warn "No guideline corpus - Evidence Advisor will say so. Other layers unaffected."
}

# --------------------------------------------------------------------------
# Free the ports
# --------------------------------------------------------------------------
foreach ($port in @($BackendPort, $FrontendPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Warn "Port $port busy (pid $($c.OwningProcess)) - stopping it"
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------
Write-Step "Starting backend (loads the ECG model, 20-60s)..."
$backend = Start-Process -FilePath $VenvPython -ArgumentList "app.py" `
    -WorkingDirectory (Join-Path $Root "backend") -WindowStyle Normal -PassThru

$ready = $false
foreach ($i in 1..60) {
    Start-Sleep -Seconds 2
    if ($backend.HasExited) {
        Write-Fail "The backend process exited immediately - read the error in its window."
        exit 1
    }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Write-Fail "Backend did not answer within 2 minutes. Check its window."
    exit 1
}
Write-Ok "Backend ready on http://127.0.0.1:$BackendPort"

try {
    $rag = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/rag/health" -TimeoutSec 15
    Write-Host "       Evidence corpus: $($rag.corpus.chunks) chunks, $($rag.corpus.embeddedChunks) indexed" -ForegroundColor DarkGray
} catch {
    Write-Warn "Evidence layer not reporting - the other layers still work."
}

# --------------------------------------------------------------------------
# Frontend. Host and port live in vite.config.ts, so no CLI flags are passed:
# PowerShell strips the dashes from arguments after `--`, which silently sent
# the dev server to its default port instead.
# --------------------------------------------------------------------------
Write-Step "Starting frontend..."
Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" `
    -WorkingDirectory $Root -WindowStyle Normal

$feReady = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $feReady = $true; break }
    } catch { }
}
if ($feReady) { Write-Ok "Frontend ready" } else { Write-Warn "Frontend slow to start - check its window." }

Write-Host ""
Write-Host "  Cardios is running:" -ForegroundColor Green
Write-Host "    App              http://127.0.0.1:$FrontendPort/"
Write-Host "    Evidence Advisor http://127.0.0.1:$FrontendPort/evidence"
Write-Host "    API health       http://127.0.0.1:$BackendPort/health"
Write-Host ""
Write-Host "  Close the two new windows to stop." -ForegroundColor DarkGray
Write-Host ""
Start-Process "http://127.0.0.1:$FrontendPort/"
