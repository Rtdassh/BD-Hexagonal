# ============================================================================
#  iniciar.ps1 - Levanta los 4 motores y la aplicación (Windows)
#
#  Uso (desde la carpeta del proyecto, en PowerShell):
#     powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
#     powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Reiniciar   # borra y recrea las bases
# ============================================================================
param([switch]$Reiniciar)

$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Falla($texto) { Write-Host ""; Write-Host "ERROR: $texto" -ForegroundColor Red; exit 1 }

# 1. Docker -------------------------------------------------------------------
Paso "Verificando Docker Desktop"
docker info *> $null
if ($LASTEXITCODE -ne 0) { Falla "Docker no responde. Abra Docker Desktop, espere a que diga 'Engine running' y vuelva a ejecutar." }

# 2. Python y dependencias ----------------------------------------------------
Paso "Preparando Python"
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
    else { Falla "No se encontró Python. Instálelo desde python.org marcando 'Add python.exe to PATH'." }
    if (-not (Test-Path $py)) { Falla "No se pudo crear el entorno virtual .venv" }
}
& $py -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Falla "No se pudieron instalar las dependencias (requirements.txt)." }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Se creó .env a partir de .env.example" }

# 3. Motores ------------------------------------------------------------------
if ($Reiniciar) {
    Write-Host ""
    Write-Host "ATENCIÓN: -Reiniciar BORRA todos los datos de las 4 bases (pacientes, consultas, cobros...)" -ForegroundColor Yellow
    Write-Host "y las vuelve a crear con los datos de ejemplo. Para trabajar normal, ejecute sin -Reiniciar." -ForegroundColor Yellow
    $resp = Read-Host "Escriba BORRAR para continuar (o Enter para iniciar sin borrar)"
    if ($resp -ne "BORRAR") { $Reiniciar = $false; Write-Host "No se borró nada." -ForegroundColor Green }
}
if ($Reiniciar) {
    Paso "Borrando las bases anteriores (docker compose down -v)"
    docker compose down -v --remove-orphans
    # A veces Docker Desktop no alcanza a borrar la red ("Error Delete .../networks/...").
    # No afecta a los datos: se reintenta y, si sigue ahí, "up" la vuelve a usar.
    $red = "$((Split-Path -Leaf $PWD).ToLower())_default"
    if (docker network ls -q --filter "name=^$red$") {
        Start-Sleep -Seconds 2
        docker network rm $red 2>$null | Out-Null
    }
}
Paso "Levantando los motores (la primera vez tarda varios minutos)"
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Falla "docker compose falló. Revise el mensaje de arriba (¿puerto ocupado?)." }

Paso "Esperando a que los motores estén listos"
$contenedores = @("bd2_postgres_hospital", "bd2_mysql_pediatrico", "bd2_mongo_laboratorio")
$limite = (Get-Date).AddMinutes(6)
foreach ($c in $contenedores) {
    do {
        $estado = (docker inspect -f "{{.State.Health.Status}}" $c 2>$null)
        if ($estado -eq "healthy") { Write-Host "  $c listo" -ForegroundColor Green; break }
        if ((Get-Date) -gt $limite) { Falla "$c no quedó listo. Vea: docker compose logs $($c.Split('_')[1])" }
        Start-Sleep -Seconds 3
    } while ($true)
}
do {
    $ok = $false
    try { $t = New-Object Net.Sockets.TcpClient; $t.Connect("localhost", 8085); $t.Close(); $ok = $true } catch { }
    if ($ok) { Write-Host "  bd2_firestore_odontologia listo" -ForegroundColor Green; break }
    if ((Get-Date) -gt $limite) { Falla "El emulador de Firestore no respondió. Vea: docker compose logs firestore" }
    Start-Sleep -Seconds 3
} while ($true)
Start-Sleep -Seconds 3

Paso "Cargando datos iniciales de Firestore (solo si está vacío)"
& $py database\firebase\seed_firestore.py

# 4. Aplicación ---------------------------------------------------------------
Paso "Iniciando la aplicación en http://localhost:5000  (Ctrl+C para detener)"
Start-Job -ScriptBlock { Start-Sleep -Seconds 5; Start-Process "http://localhost:5000" } | Out-Null
& $py src\main.py
