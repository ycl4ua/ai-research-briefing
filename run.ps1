$ErrorActionPreference = "Stop"

$BundledPython = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Python = $null

if (Test-Path -LiteralPath $BundledPython) {
  $Python = $BundledPython
}

if (-not $Python) {
  $Candidates = @("py", "python")
  foreach ($Candidate in $Candidates) {
    $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if (-not $Command) {
      continue
    }

    & $Candidate --version *> $null
    if ($LASTEXITCODE -eq 0) {
      $Python = $Candidate
      break
    }
  }
}

if (-not $Python) {
  throw "Python was not found. Install Python or run with Codex bundled Python."
}

& $Python "$PSScriptRoot\pipeline\ai_briefing.py" --refresh
if ($LASTEXITCODE -ne 0) {
  throw "Digest refresh failed."
}

Write-Host "Serving AI Research Briefing at http://127.0.0.1:8080/app/index.html"
& $Python -m http.server 8080 -d "$PSScriptRoot"
