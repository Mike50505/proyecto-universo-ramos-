param([int]$Port = 0)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath '.env')) {
    throw 'Falta .env. Copie .env.example y configure los secretos.'
}

docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker no responde en esta sesion de Windows.'
}

$reusePort = $false
if ($Port -le 0) {
    $portLine = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^APP_PORT=\d+$' } | Select-Object -First 1
    if ($portLine) {
        $existingPort = [int]($portLine -replace '^APP_PORT=', '')
        try {
            $existingResponse = Invoke-WebRequest -Uri "http://localhost:$existingPort/login/" -UseBasicParsing -TimeoutSec 3
            if ($existingResponse.StatusCode -eq 200 -and $existingResponse.Content -match 'Universo Ramos') {
                $Port = $existingPort
                $reusePort = $true
            }
        } catch {}
    }
}

function Test-PortAvailable([int]$Candidate) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Candidate)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Set-AppPort([int]$ChosenPort) {
    $environmentFile = Get-Content -Raw -LiteralPath '.env'
    if ($environmentFile -match '(?m)^APP_PORT=') {
        $environmentFile = [regex]::Replace($environmentFile, '(?m)^APP_PORT=.*$', "APP_PORT=$ChosenPort")
    } else {
        $environmentFile = $environmentFile.TrimEnd() + [Environment]::NewLine + "APP_PORT=$ChosenPort" + [Environment]::NewLine
    }
    Set-Content -LiteralPath '.env' -Value $environmentFile -NoNewline
}

$started = $false
for ($attempt = 1; $attempt -le 8; $attempt++) {
    if ($Port -le 0 -or $attempt -gt 1 -or (-not $reusePort -and -not (Test-PortAvailable $Port))) {
        do {
            $Port = Get-Random -Minimum 40000 -Maximum 60000
        } until (Test-PortAvailable $Port)
        $reusePort = $false
    }
    Set-AppPort $Port
    Write-Host "Intento $attempt : publicando en el puerto $Port"
    docker compose up --build -d
    if ($LASTEXITCODE -eq 0) {
        $started = $true
        break
    }
    Write-Warning "Docker rechazo el puerto $Port o no pudo iniciar. Probando otro puerto."
}
if (-not $started) { throw 'Docker Compose no pudo iniciar despues de ocho intentos. Revise el error anterior.' }
$url = "http://localhost:$Port/login/"
$ready = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    docker compose ps
    docker compose logs --tail=100 web
    throw "Los contenedores iniciaron, pero $url no respondio con HTTP 200. Revise docker compose logs web."
}
$style = Invoke-WebRequest -Uri "http://localhost:$Port/static/app.css" -UseBasicParsing -TimeoutSec 10
if ($style.StatusCode -ne 200 -or -not $style.Content.Contains('.view-switch')) {
    throw 'La aplicacion responde, pero sirve una version anterior sin Vista Excel. Revise docker compose logs web y vuelva a ejecutar este script.'
}
docker compose exec -T web python manage.py setup_roles
if ($LASTEXITCODE -ne 0) { throw 'La aplicacion inicio, pero fallo la creacion de roles.' }
if ((Get-Content -Raw -LiteralPath '.env') -match '(?m)^BOOTSTRAP_ADMIN_HASH=') {
    docker compose exec -T web python manage.py bootstrap_admin
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear administrator. Revise el mensaje anterior.' }
    $environmentFile = Get-Content -Raw -LiteralPath '.env'
    $environmentFile = [regex]::Replace($environmentFile, '(?m)^BOOTSTRAP_ADMIN_HASH=.*\r?\n?', '')
    Set-Content -LiteralPath '.env' -Value $environmentFile -NoNewline
}
Write-Host "Universo Ramos disponible en $url"
