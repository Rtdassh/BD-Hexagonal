# Red de historiales clínicos — Proyecto final Bases de Datos II

Aplicación cliente-servidor con **arquitectura hexagonal**: la misma lógica de negocio
(registrar consulta, agregar diagnóstico, recetar medicamento, dar de baja) se ejecuta
sobre cuatro motores distintos. Al iniciar sesión, el enrutador dirige las operaciones
del usuario al motor de su institución.

| Institución | Motor | Por qué |
|---|---|---|
| Hospital General | **PostgreSQL** | Citas, diagnósticos y tratamientos con integridad transaccional fuerte (ACID, llaves foráneas, CHECK). |
| Centro Médico Pediátrico | **MySQL (InnoDB)** | Consultas cortas y frecuentes con estructura fija (somatometría, vacunas); InnoDB da transacciones y FK con poca administración. |
| Laboratorio Clínico | **MongoDB** | Cada examen tiene parámetros distintos (hematología ≠ orina ≠ cultivo): el documento flexible evita decenas de tablas o columnas nulas. |
| Clínica Odontológica | **Firebase Firestore** | Clínica pequeña sin personal técnico: servicio administrado, sin servidor que mantener, rápido para la recepción. |

---

## 1. Requisitos (Windows)

- **Python 3.11 o superior** — al instalar, marque *Add python.exe to PATH*.
- **Docker Desktop** (con WSL 2). Ábralo y espere a que diga *Engine running*.
- Git / GitHub Desktop.

## 2. Puesta en marcha (paso a paso)

**Atajo:** con Docker Desktop abierto, este script hace todos los pasos de abajo, espera a que los
motores estén listos y abre el navegador:

```powershell
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1             # iniciar
powershell -ExecutionPolicy Bypass -File .\iniciar.ps1 -Reiniciar  # borrar y recrear las bases
```

Paso a paso manual:

Abra **PowerShell** en la carpeta del proyecto (en GitHub Desktop: *Repository → Open in Command Prompt*, o desde VS Code: *Terminal → New Terminal*).

```powershell
# 1. Entorno virtual de Python e instalación de drivers
py -m venv .venv
.venv\Scripts\Activate.ps1          # si da error de permisos: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

# 2. Variables de entorno
copy .env.example .env

# 3. Levantar los 4 motores (la primera vez descarga imágenes y crea las bases: 3-8 minutos)
docker compose up -d --build
docker compose ps                    # espere a que postgres, mysql y mongo digan "healthy"

# 4. Cargar los datos de la clínica odontológica en Firestore
python database/firebase/seed_firestore.py

# 5. Iniciar la aplicación
python src/main.py
```

Abra **http://localhost:5000**. En la consola debe ver los 4 motores como `REAL`:

```
[REAL     ] Hospital General             PostgreSQL
[REAL     ] Centro Médico Pediátrico     MySQL
[REAL     ] Laboratorio Clínico          MongoDB
[REAL     ] Clínica Odontológica         Firebase Cloud Firestore
```

Si alguno dice `SIMULADO`, ese motor no respondió y la app usa datos en memoria para no caerse.
La línea `motivo:` dice por qué. Para la presentación ponga `ENGINE_MODE=live` en `.env`: así la app
no arranca si falta un motor, y no hay dudas de que todo es real.

**Usuarios** (contraseña `123`): un administrador por institución — `admin_hospital`, `admin_pediatria`,
`admin_laboratorio` y `admin_odontologia`. Cada uno solo accede al motor de su institución.

Los doctores **no inician sesión**: el administrador los registra en **Personal médico** (médicos, pediatras,
laboratoristas u odontólogos según la institución) y los asigna a cada cita y consulta. Un profesional no se
borra, porque sus citas y consultas quedan en los historiales: se desactiva, y deja de aparecer al agendar.

### Pruebas

```powershell
python -m pytest tests -v
```

`tests/test_motores_reales.py` corre **el mismo flujo** (registrar paciente, cita, consulta con diagnóstico,
cita repetida rechazada, filtro de secretaria, baja y bloqueo) contra los 4 motores reales.

### Hospital General: quirófanos y enfermería

Solo el administrador del hospital ve dos secciones extra en el menú:

- **Quirófanos**: tablero de QX-1, QX-2 y QX-3 (libre o en uso), agenda del día, pendientes y búsqueda por fecha.
  Una cirugía pasa por *programada → en curso → realizada* o *cancelada*. PostgreSQL rechaza programar dos
  cirugías que se traslapen en el mismo quirófano o con el mismo cirujano.
- **Enfermería**: pacientes ingresados por turno (mañana 07–15, tarde 15–23, noche 23–07) con sus enfermeros
  asignados y la carga de cada enfermero. Máximo 6 pacientes por enfermero por turno y solo pacientes ingresados
  (lo verifica un trigger de PostgreSQL).
- En **Personal médico** hay una pestaña para **Enfermeros**, y en cada paciente la pestaña
  **Internamiento y cirugías** permite registrar el egreso (alta o referido), asignar enfermeros y programar cirugías.

---

## 3. Cómo se crea y se conecta cada base

Docker ejecuta automáticamente los scripts de `database/` **solo la primera vez** (cuando el volumen está vacío).

| Motor | Puerto en su PC | Scripts de creación | Usuario de la app | Driver Python |
|---|---|---|---|---|
| PostgreSQL 16 | `5433` | `postgresql/01_init_hospital.sql`, `02_cirugias_enfermeria.sql`, `03_seguridad_hospital.sql` | `app_hospital` | `psycopg2` (pool de conexiones) |
| MySQL 8.4 | `3307` | `mysql/01_init_pediatrico.sql`, `02_seguridad_pediatrico.sql` | `app_pediatrico` | `mysql-connector-python` (pool) |
| MongoDB 7 (replica set `rs0`) | `27018` | `mongodb/01_init_laboratorio.js` | `app_laboratorio` | `pymongo` |
| Firestore (emulador) | `8085` (UI en `4000`) | `firebase/seed_firestore.py` + `firestore.rules` | — | `google-cloud-firestore` / `firebase-admin` |

Los puertos no son los estándar para no chocar con un PostgreSQL o MySQL que ya tenga instalado.
Las contraseñas están en `.env` (no se sube a Git).

**Ver los datos con un cliente gráfico** (DataGrip, pgAdmin, MySQL Workbench, MongoDB Compass):

- PostgreSQL: host `localhost`, puerto `5433`, base `hospital_db`, usuario `postgres` / `postgres` (administrador) — esquema `hospital`.
- MySQL: host `127.0.0.1`, puerto `3307`, usuario `root` / `root` — base `centro_pediatrico`.
- MongoDB (Compass): `mongodb://root:root@localhost:27018/?directConnection=true`
- Firestore: abra **http://localhost:4000** (interfaz del emulador).

**Recrear las bases desde cero** (por ejemplo, si cambia un script):

```powershell
docker compose down -v      # -v borra los volúmenes con los datos
docker compose up -d --build
python database/firebase/seed_firestore.py
```

### Usar un proyecto real de Firebase (en lugar del emulador)

1. En https://console.firebase.google.com cree un proyecto y active **Cloud Firestore** (modo producción).
2. *Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada*. Guarde el JSON **fuera** del repositorio.
3. En `.env`: borre la línea `FIRESTORE_EMULATOR_HOST`, ponga `FIREBASE_PROJECT_ID=<id de su proyecto>` y
   `FIREBASE_CREDENTIALS_PATH=C:/ruta/a/la/clave.json`.
4. Publique las reglas: copie `database/firebase/firestore.rules` en *Firestore → Reglas*.
5. Ejecute `python database/firebase/seed_firestore.py`.

---

## 4. Problemas comunes

| Síntoma | Solución |
|---|---|
| `port is already allocated` | Otro programa usa ese puerto. Cambie el primer número en `docker-compose.yml` (p. ej. `"5434:5432"`) y el mismo valor en `.env`. |
| Mongo aparece `SIMULADO` o `docker compose ps` no dice *healthy* | Espere 30 s (el replica set se inicia en el primer chequeo). Si sigue: `docker compose logs mongo`. |
| Mongo dice "Sin replica set" en *Estado de los motores* | Funciona, pero sin transacciones multi-documento. Verifique que usa el `docker-compose.yml` del proyecto. |
| Firestore `SIMULADO` | El contenedor tarda en compilarse la primera vez: `docker compose logs firestore`. Verifique `FIRESTORE_EMULATOR_HOST=localhost:8085` en `.env`. |
| Los datos de Firestore desaparecieron | El emulador guarda al apagarse con `docker compose stop` o `down`. Si Docker se cerró de golpe, vuelva a correr `seed_firestore.py`. |
| Las horas salen 6 horas adelantadas | Recree las bases (`-Reiniciar`): el `docker-compose.yml` ya fija la zona horaria de Guatemala. |
| Cambié un `.sql` y no se refleja | Los scripts solo corren con volumen vacío: `docker compose down -v` y vuelva a levantar. |
| Acentos raros en MySQL | Recree la base (el script ya usa `SET NAMES utf8mb4`). |

---

## 5. Estructura (arquitectura hexagonal)

```
src/
  domain/          entidades y PUERTOS (ClinicalRepositoryPort, AuthPort) — no conoce ningún motor
  application/     servicios (reglas de negocio comunes) y router.py (elige el adaptador por usuario)
  infrastructure/
    adapters/      un ADAPTADOR por motor: postgresql_, mysql_, mongodb_, firebase_adapter.py
      simulated/   adaptadores en memoria (respaldo y modo demo)
    config.py      lectura de .env y usuarios
  interfaces/      API REST (Flask) y la interfaz web (static/)
database/          scripts de creación de cada motor
```

Reglas de negocio que viven en `application/services.py` y aplican igual a los 4 motores:
solo el administrador gestiona el personal médico; toda cita y consulta se asigna a un profesional
**activo** de la institución; no se receta sin diagnóstico; un historial dado de baja no admite registros
nuevos. El filtro de información restringida (rol secretaria) sigue en el código para cuando se agreguen
cuentas con permisos limitados.

---

## 6. Resumen para el documento comparativo

**Modelado**

- *PostgreSQL*: 3FN. `Receta → Tratamiento → Diagnóstico → Consulta → Cita → Paciente`; catálogos de `Medicamento` y `Especialidad`. Quirófanos y enfermería: `Quirofano`, `Cirugia` (paciente, cirujano, hospitalización, quirófano), `Enfermero` y `Asignacion_Turno` (enfermero × hospitalización × fecha × turno).
- *MySQL*: el diagnóstico principal y la somatometría van en la fila de `consulta` (una consulta pediátrica es corta y tiene un diagnóstico); `vacunacion` y `receta` son tablas hijas. La dosis en ml se calcula con el peso (mg/kg × kg ÷ mg/ml).
- *MongoDB*: `resultados` se **referencian** (un paciente acumula cientos de exámenes; embeberlos haría crecer el documento del paciente sin límite, y MongoDB limita a 16 MB). Los `parametros` de cada resultado se **embeben** (siempre se leen juntos y su estructura cambia por examen; la plantilla vive en `tipos_examen`). El contacto de emergencia se embebe (1:1).
- *Firestore*: el historial se **embebe** en el documento del paciente (1:1). Las consultas son una **subcolección** `pacientes/{id}/consultas` (crecen sin límite; Firestore limita a 1 MB por documento). Cada consulta embebe sus diagnósticos, recetas y procedimientos por pieza. `citas` es colección raíz con el nombre del paciente **duplicado** para que la secretaria liste la agenda con una sola lectura.

**Consistencia**

- *PostgreSQL / MySQL*: `BEGIN … COMMIT/ROLLBACK`; `SELECT … FOR UPDATE` sobre la cita y el historial para que dos usuarios no atiendan la misma cita. Restricciones `CHECK`, `UNIQUE` y llaves foráneas.
- *PostgreSQL (hospital)*: restricciones `EXCLUDE USING gist` con rangos de tiempo (`tsrange … WITH &&`) para que un quirófano o un cirujano no tengan dos cirugías activas traslapadas; un trigger `BEFORE INSERT` limita a 6 pacientes por enfermero por turno; un índice único parcial evita asignaciones duplicadas. Las asignaciones se anulan en vez de borrarse. Son garantías que la base hace cumplir aunque la aplicación falle.
- *MongoDB*: transacción multi-documento (orden + muestra + resultado + historial) con sesión, que requiere replica set. Índices únicos (DPI, ids) y validación `$jsonSchema`. Ids secuenciales con `$inc` atómico en `contadores`.
- *Firestore*: transacciones (todas las lecturas antes que las escrituras; Firestore reintenta si otro cliente cambió algo). La unicidad del DPI se garantiza leyendo `dpi_index/{dpi}` dentro de la transacción. La carga inicial usa un *batch* atómico.

**Seguridad**

- *PostgreSQL / MySQL*: usuario de aplicación con `SELECT, INSERT, UPDATE` y **sin DELETE** ni DDL (los historiales nunca se borran, se archivan).
- *MongoDB*: autenticación activada; usuario `app_laboratorio` con rol `readWrite` solo en su base.
- *Firestore*: `firestore.rules` por rol (pública: catálogos; confidencial: pacientes y citas; restringida: consultas solo para el odontólogo; `delete` prohibido). El backend usa una cuenta de servicio (Admin SDK), que no pasa por las reglas, así que la API también aplica los permisos.
- *Aplicación*: token de sesión aleatorio, sin acceso anónimo (401), un administrador por institución que solo llega a su motor (el parámetro `institucion` se ignora), permisos por rol (403) y credenciales fuera del código (`.env`).

> Pendiente para un sistema real: guardar los usuarios en base de datos con contraseñas cifradas (bcrypt)
> en lugar de la lista de demostración en `config.py`.
