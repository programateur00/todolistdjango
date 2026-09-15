<#
Compila el APK de DEBUG y lo instala directo en el movil por USB (o por
adb-wifi si ya lo tienes emparejado) -- para el dia a dia de probar
ejercicio por ejercicio sin pasar por PythonAnywhere ni tocar numeros de
version. Eso queda solo para cuando publiques de verdad con release.ps1.

Requiere:
    - El movil conectado (USB con depuracion activada, o ya conectado por
      "adb connect ip:puerto" si usas depuracion inalambrica).
    - "adb" en el PATH -- viene con Android Studio, dentro de
      .../Android/Sdk/platform-tools. Si "adb" no se reconoce, anade esa
      carpeta a tu PATH o usa la ruta completa una vez.

Uso:
    .\probar-usb.ps1
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "== 0/3 Comprobando que hay un movil conectado =="
$devices = (adb devices) -split "`n" | Select-String "\tdevice$"
if (-not $devices) {
    throw "adb no ve ningun movil. Prueba 'adb devices' a mano -- revisa el cable, o que la depuracion USB/inalambrica siga activada y autorizada en el telefono."
}

Write-Host "== 1/3 Copiando www/ al proyecto Android =="
npx cap copy android
if ($LASTEXITCODE -ne 0) { throw "npx cap copy android ha fallado." }

Write-Host "== 2/3 Compilando APK de debug (gradlew assembleDebug) =="
Push-Location (Join-Path $root "android")
try {
    & .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) { throw "gradlew assembleDebug ha fallado." }
} finally {
    Pop-Location
}

$apk = Join-Path $root "android\app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $apk)) {
    throw "gradlew ha terminado pero no encuentro el APK en $apk -- revisa la salida de arriba."
}

Write-Host "== 3/3 Instalando en el movil por adb =="
adb install -r "$apk"
if ($LASTEXITCODE -ne 0) {
    throw "adb install ha fallado. En Xiaomi/MIUI a veces hace falta activar ademas 'Instalar via USB' dentro de Ajustes de desarrollador -> Configuracion de seguridad USB."
}

Write-Host ""
Write-Host "Listo -- instalado directamente en el movil, sin pasar por PythonAnywhere."
Write-Host "(Esto NO ha subido version.js ni build.gradle -- para publicar de verdad, usa .\release.ps1 como siempre.)"
