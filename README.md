# Universo Ramos

Catálogo central de números de parte con interfaz Django, PostgreSQL y API de lectura para MESA, EDH y otros consumidores. Las órdenes, inventarios, rutas, documentos y otros datos operativos permanecen en sus aplicaciones.

## Versiones

- Python 3.12
- Django 5.2.17 (rama LTS 5.2)
- Django REST Framework 3.16.1
- PostgreSQL 17 (imagen oficial `postgres:17`)
- psycopg 3.2.10, openpyxl 3.1.5, Gunicorn 23.0.0 y WhiteNoise 6.9.0 para archivos estáticos

## Inicio

1. Copie `.env.example` a `.env`. Genere una clave aleatoria para `DJANGO_SECRET_KEY` y cambie la contraseña de PostgreSQL.
2. Ejecute `docker compose up --build -d`.
3. Ejecute `docker compose exec web python manage.py setup_roles`.
4. Ejecute `docker compose exec web python manage.py createsuperuser`.
5. Abra `http://localhost:38080/login/` (o el puerto definido en `APP_PORT`). La pantalla inicial es el catálogo.

En Windows, `powershell -ExecutionPolicy Bypass -File .\iniciar-local.ps1` ejecuta Compose desde su sesión, prueba puertos altos hasta que Docker acepte uno, crea los roles y muestra el enlace solo después de recibir HTTP 200.

Las migraciones se aplican al arrancar el servicio web. Para pruebas: `docker compose exec web python manage.py test`. Los datos de referencia no se importan automáticamente. La plantilla se descarga desde **Importaciones**.

## Modelo y decisiones sobre el Excel

El archivo `UNIVERSO RAMOS.XLSX` incluye `Sheet1` (302 códigos únicos) y `Sheet1 (2)` (305 filas con código, 301 códigos únicos y cuatro códigos repetidos). Ambas hojas comparten 301 códigos. Los encabezados están en la fila 2 y `CLIENTE` aparece dos veces, en columnas B y L. La columna B alimenta el catálogo de cliente; la segunda aparición y `PLANTA` se conservan como textos independientes sin deducir una relación por pieza. No se importan automáticamente.

La guía de MESA declara que el número de parte no se repite en el catálogo. Por eso `normalized_number` tiene una restricción única global. La normalización aplica Unicode NFKC, elimina espacios solo en los extremos y convierte a mayúsculas; mantiene guiones, ceros iniciales y espacios interiores. Se conserva el código original mostrado. Si la empresa identifica códigos iguales para clientes distintos, debe revisarse esta regla antes de cargar tales registros. Los duplicados del libro quedan bloqueados para revisión.

`diameter` es texto para preservar expresiones como `A - 3/8`. `wall` y `weight` son decimales sin unidad inferida. Cuatro filas de `Sheet1` contienen `PARED = NO`: se conserva ese texto en `wall_note`, mientras que `wall` queda nulo; no se interpreta su significado. `std` es texto sin significado supuesto. `NULL` expresa dato ausente y es diferente de cero. Cliente, destino, caja y hoja color son catálogos; no se deduce ninguna asociación entre cliente, destino y planta. No hay borrado físico desde la interfaz.

## Roles

`Administrador` gestiona todo, incluidos usuarios y claves de integración. `Editor` gestiona piezas, catálogos relacionados e importaciones. `Consulta` solo lee el catálogo. Un superusuario equivale a Administrador. Los permisos se comprueban en las vistas, no solo en el menú.

## Importación

Suba un `.xlsx` de hasta 5 MB, elija una hoja, revise el mapeo y seleccione un modo. En el libro de referencia se propone la primera columna `CLIENTE` para el cliente principal y la segunda para el texto adicional, siempre con revisión visible antes de confirmar. La vista previa muestra todas las columnas del Excel, altas, cambios anteriores/nuevos, filas sin cambios, duplicados y errores. Los valores nuevos de cliente, destino, caja y hoja color se muestran en la vista previa y se crean únicamente al confirmar, en la misma transacción que las piezas. La vista previa no modifica piezas ni catálogos. Si existen errores o duplicados, la confirmación se bloquea. Al confirmar se compara de nuevo el análisis y se aplican todos los cambios en una transacción. Una segunda confirmación del mismo trabajo no aplica cambios adicionales. Celdas vacías no borran valores existentes salvo que se active la opción explícita.

Para cargar el archivo tal como está, elija `Sheet1` y el modo **Agregar y actualizar**. La hoja `Sheet1 (2)` mantiene sus duplicados bloqueados para revisión. Las 52 piezas que se hayan cargado previamente se compararán por código: se actualizarán si hay diferencias; las demás se añadirán. La opción **Vista Excel** del catálogo y el CSV de exportación muestran ambas columnas `CLIENTE` y `PLANTA`.

Las fórmulas en campos mapeados se rechazan y nunca se evalúan; solo se aceptan `.xlsx`, no archivos con macros. El informe de incidencias descarga filas y motivos. La plantilla descargable incluye las columnas compartidas y las dos columnas adicionales conservadas como texto.

## API y sincronización

Vea [docs/API.md](docs/API.md) y [docs/openapi.yaml](docs/openapi.yaml). Las claves se crean desde **Integraciones**, se muestran una sola vez y solo se almacena SHA-256 del token completo. La aplicación consumidora lo envía por HTTPS como `Authorization: Bearer ...`. Cada clave puede revocarse. No hay CORS abierto ni token en JavaScript del navegador.

El ejemplo [scripts/sample_consumer.py](scripts/sample_consumer.py) crea una caché SQLite local con operaciones idempotentes y guarda el cursor en la misma transacción que aplica los cambios. MESA y EDH deben conservar sus claves y relaciones locales, enlazando el UUID central; deben mantener sus propias copias históricas de órdenes, cierres y documentos. Un cambio del catálogo no reescribe esos registros pasados.

## Producción

Use `DJANGO_DEBUG=0`, un secreto fuerte, `DJANGO_ALLOWED_HOSTS` con dominios reales, `DJANGO_CSRF_TRUSTED_ORIGINS=https://...` y `DJANGO_SECURE_SSL_REDIRECT=1`. Termine TLS en un proxy confiable y envíe `X-Forwarded-Proto`; configure certificados y redirección HTTP a HTTPS allí. Las cookies de sesión y CSRF se marcan seguras cuando DEBUG está apagado. Restrinja el puerto de PostgreSQL a la red privada y guarde `.env` fuera de control de versiones. La aplicación no registra cuerpos de solicitudes ni claves.

## Respaldo y restauración

Respaldo: `docker compose exec -T db pg_dump -U universo -Fc universo_ramos > universo.dump`.

Restauración a una base vacía: `docker compose exec -T db pg_restore -U universo -d universo_ramos --clean --if-exists < universo.dump`. Ajuste usuario y base a su `.env`, detenga escrituras durante la restauración y verifique el resultado antes de reanudar integraciones. Respalde también el volumen de archivos de importación si necesita conservar los originales.

## Verificación de este entorno

Se generaron las migraciones `0001` a `0004`. Se ejecutaron ocho pruebas de catálogo, permisos, formularios e importación en SQLite temporal, incluida la confirmación de las 302 filas de `Sheet1` y el bloqueo de los duplicados de `Sheet1 (2)`. Este entorno de Codex no puede conectar con el daemon Docker de Windows; tras reconstruir, ejecute `docker compose exec web python manage.py test` y pruebe los flujos en PostgreSQL.
