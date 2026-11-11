$ErrorActionPreference='Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
 & (Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe') '/nologo' '/target:winexe' '/platform:x64' '/optimize+' '/out:HDC_Setup_1.4.exe' '/win32icon:Product.ico' '/win32manifest:installer.manifest' '/r:System.Windows.Forms.dll' '/r:System.Drawing.dll' '/r:System.IO.Compression.dll' '/r:System.IO.Compression.FileSystem.dll' '/resource:Logo.png,Product.Logo.png' '/resource:Photo.png,Product.Photo.png' 'InstallerCore.cs' 'ProductOperations.cs' 'ProductConfig.cs' 'InstallerWizard.cs' 'PayloadIdentity.cs'
 if($LASTEXITCODE -ne 0){throw 'Build failed'}
 Copy-Item -LiteralPath 'HDC_Setup_1.4.exe' -Destination (Join-Path $PSScriptRoot '..') -Force
} finally {Pop-Location}
