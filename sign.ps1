# sign.ps1 — пересборка и подпись LinguaPilot self-signed сертификатом ilabolAfk
# Использование:
#   powershell -ExecutionPolicy Bypass -File sign.ps1            # сборка + подпись
#   powershell -ExecutionPolicy Bypass -File sign.ps1 -SkipBuild  # только подпись (exe уже собраны)
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
$SUBJECT = "ilabolAfk"

if (-not $SkipBuild) {
    Write-Host "== Rebuilding EXEs ==" -ForegroundColor Cyan
    & python build.py
    if ($LASTEXITCODE -ne 0) { throw "build.py failed" }
}

Write-Host "== Finding code-signing cert ==" -ForegroundColor Cyan
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Where-Object { $_.Subject -match $SUBJECT } | Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $cert) {
    Write-Host "No cert found. Using cached PFX... " -ForegroundColor Yellow
    $pfx = "ilabolAfk-code-signing.pfx"
    if (Test-Path $pfx) {
        $pwd = ConvertTo-SecureString "ilabolAfk-2026" -Force -AsPlainText
        $cert = Import-PfxCertificate -FilePath $pfx -CertStoreLocation Cert:\CurrentUser\My -Password $pwd
    } else {
        throw "No code-signing cert or PFX found."
    }
}

Write-Host "== Ensuring cert trusted (Root + TrustedPublisher) ==" -ForegroundColor Cyan
foreach ($storeName in @([System.Security.Cryptography.X509Certificates.StoreName]::Root,
                         [System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)) {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, "CurrentUser")
    $store.Open("ReadWrite")
    $exists = $store.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if (-not $exists) { $store.Add($cert) }
    $store.Close()
}

Write-Host "== Signing EXEs ==" -ForegroundColor Cyan
$files = @("dist\lingua-pilot-server.exe","dist\LinguaPilot.exe","installer\LinguaPilot-Setup.exe")
$allValid = $true
foreach ($f in $files) {
    if (Test-Path $f) {
        Set-AuthenticodeSignature -FilePath $f -Certificate $cert | Out-Null
        $st = (Get-AuthenticodeSignature $f).Status
        Write-Host ("  {0} -> {1}" -f $f, $st)
        if ($st -ne "Valid") { $allValid = $false }
    } else {
        Write-Host ("  SKIP (not found): {0}" -f $f) -ForegroundColor DarkGray
    }
}

Write-Host ""
if ($allValid) {
    Write-Host "All files signed and Valid." -ForegroundColor Green
} else {
    Write-Host "Some files NOT Valid. Check output above." -ForegroundColor Red
}