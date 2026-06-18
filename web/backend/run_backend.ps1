<#
Helper script to check Python version and run the backend.
Usage: from the repo root run `powershell -File web\backend\run_backend.ps1`
#>
function Get-PythonInfo {
    $pyCmds = @('py -3.11', 'py -3.10', 'python')
    foreach ($c in $pyCmds) {
        try {
            $out = & cmd /c "$c -c \"import sys, json; print(json.dumps(list(sys.version_info[:3])) )\"" 2>$null
            if ($out) { return @{cmd=$c; ver=($out | ConvertFrom-Json)} }
        } catch { }
    }
    return $null
}

$info = Get-PythonInfo
if (-not $info) {
    Write-Host "Python 3.11 or 3.10 not found. Please install Python 3.11 and re-run." -ForegroundColor Yellow
    exit 1
}

Write-Host "Using Python command: $($info.cmd) version: $($info.ver -join '.')"

Write-Host "Create and activate a venv (if not already):"
Write-Host "  cd web\backend"
Write-Host "  $($info.cmd) -m venv .venv"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Install requirements:"
Write-Host "  python -m pip install --upgrade pip"
Write-Host "  python -m pip install -r requirements.txt"
Write-Host "To start the server run from the web root:"
Write-Host "  cd web"
Write-Host "  .\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
