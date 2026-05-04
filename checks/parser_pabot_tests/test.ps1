# PR check: same command, two pabot versions.
# Shows why the patch matters for custom parser discovery.

$env:PYTHONPATH = (Get-Location).Path
$checksRoot = $PSScriptRoot
$demoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\test_EAI - Copie\sandbox_parser_demo")
$samplePath = Join-Path $checksRoot "sample.demo"

function Clear-Outputs {
	Remove-Item ".pabotsuitenames", "pabot_results", "output.xml", "log.html", "report.html" -Recurse -Force -ErrorAction SilentlyContinue
}

$childCommand = @(".\venv_patched\Scripts\python.exe", "-m", "robot")

Clear-Outputs

Push-Location $demoRoot

Write-Host "Test 1: Official pabot 5.2.2 (no patch)"
& (Join-Path $demoRoot "venv\Scripts\python.exe") -m pabot.pabot --processes 1 --outputdir $checksRoot --command $childCommand --end-command --parser demo_parser.DemoParser $samplePath 2>&1 | Select-String "Suite 'Sample' contains no tests or tasks\."
Write-Host ""

Clear-Outputs

Write-Host "Test 2: Patched pabot 5.2.2 (with custom_parsers fix)"
& (Join-Path $demoRoot "venv_patched\Scripts\python.exe") -m pabot.pabot --processes 1 --outputdir $checksRoot --command $childCommand --end-command --parser demo_parser.DemoParser $samplePath

Pop-Location
