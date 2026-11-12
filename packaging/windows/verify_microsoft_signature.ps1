param([Parameter(Mandatory = $true)][string]$FilePath)
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -LiteralPath $FilePath
if ($signature.Status -ne 'Valid' -or
    $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw "The WebView2 bootstrapper does not have a valid Microsoft Authenticode signature."
}
Write-Host 'Microsoft WebView2 bootstrapper signature verified.'
