$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

function New-VenvWith {
    param([string]$Exe, [string[]]$ExtraArgs)
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $false }
    if (Test-Path .\.venv) { Remove-Item -Recurse -Force .\.venv }
    $argList = $ExtraArgs + @("-m", "venv", ".venv")
    $proc = Start-Process -FilePath $Exe -ArgumentList $argList -NoNewWindow -Wait -PassThru
    return ($proc.ExitCode -eq 0 -and (Test-Path .\.venv\Scripts\python.exe))
}

if (-not (Test-Path .\.venv)) {
    $created = $false
    foreach ($pair in @(
        @("py", @("-3")),
        @("py", @()),
        @("python3", @()),
        @("python", @())
    )) {
        $exe = $pair[0]
        $extra = $pair[1]
        if (New-VenvWith -Exe $exe -ExtraArgs $extra) {
            $created = $true
            break
        }
    }
    if (-not $created) {
        Write-Error "Could not create .venv. 'py' may point to a removed Python (e.g. Python312). Reinstall from https://python.org or run: python -m venv .venv"
        exit 1
    }
    .\.venv\Scripts\pip.exe install -r requirements.txt
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Error "No .venv found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
