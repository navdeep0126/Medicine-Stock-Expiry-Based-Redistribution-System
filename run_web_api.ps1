$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

# Fail-safe: the web API will refuse any database other than the test DB.
$env:MEDICINE_DB_NAME = 'medicine_redistribution_test_db'

if (-not $env:MEDICINE_DB_PASSWORD) {
    $secure = Read-Host 'Enter your MySQL password (input is hidden)' -AsSecureString
    $env:MEDICINE_DB_PASSWORD = [System.Net.NetworkCredential]::new('', $secure).Password
}

if (-not $env:MEDICINE_DB_PASSWORD) {
    throw 'MySQL password was not provided. Nothing was started.'
}

python .\web_api.py
