$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3.12 -m venv .venv }
if (!(Test-Path '.venv\Scripts\python.exe')) { throw '请先安装 Python 3.12，然后重新运行。' }
& '.\.venv\Scripts\python.exe' -m pip install -r oralscan-server/requirements.txt
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查上方提示。' }
Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList 'oralscan-server/server.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Start-Process 'http://localhost:8090/'
& '.\.venv\Scripts\python.exe' -m http.server 8090 --bind 127.0.0.1 --directory docs
