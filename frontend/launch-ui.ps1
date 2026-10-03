param(
  [int]$Port = 5173,
  [string]$ApiUrl = $(if ($env:VITE_API_URL) { $env:VITE_API_URL } else { "http://127.0.0.1:8000" })
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$esbuild = Join-Path $PSScriptRoot "node_modules\@esbuild\win32-x64\esbuild.exe"
if (-not (Test-Path $esbuild)) {
  throw "esbuild is missing. Run npm install in the frontend directory first."
}

$dist = Join-Path $PSScriptRoot "dist"
New-Item -ItemType Directory -Path $dist -Force | Out-Null
$apiLiteral = '"' + $ApiUrl.Replace('"', '\"') + '"'
& $esbuild src/main.tsx --bundle --minify --outfile=dist/app.js "--define:import.meta.env.VITE_API_URL=$apiLiteral"
if ($LASTEXITCODE -ne 0) { throw "Frontend bundle failed (exit $LASTEXITCODE)." }

Copy-Item index.html (Join-Path $dist "index.html") -Force
Copy-Item src\index.css (Join-Path $dist "app.css") -Force
$indexPath = Join-Path $dist "index.html"
$html = Get-Content $indexPath -Raw
$html = $html.Replace('<script type="module" src="/src/main.tsx"></script>', '<link rel="stylesheet" href="/app.css" /><script defer src="/app.js"></script>')
Set-Content -Path $indexPath -Value $html -NoNewline

Write-Host "Travel Planner UI: http://127.0.0.1:$Port (API: $ApiUrl)"
python -m http.server $Port --bind 127.0.0.1 --directory $dist
