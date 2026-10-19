# API de integración v1

Base: `/api/v1/`. Todas las rutas son GET y requieren una clave activa en `Authorization: Bearer <clave>`. La clave se crea y revoca en la pantalla **Integraciones**. Use HTTPS en producción.

| Ruta | Función |
| --- | --- |
| `GET /parts/?q=texto&customer=LENNOX%201&active=true&page=1&page_size=50` | Lista paginada y búsqueda parcial |
| `GET /parts/exact/?code=625994-01` | Búsqueda exacta normalizada; devuelve `count`, `multiple` y `results` |
| `GET /parts/{uuid}/` | Pieza por UUID, incluida si está inactiva |
| `GET /catalogs/` | Clientes, destinos, cajas y colores activos |
| `GET /bootstrap/` | Instrucciones y cursor inicial para una carga completa |
| `GET /changes/?cursor=...&limit=100` | Eventos ordenados, con `next_cursor` y `has_more` |

Ejemplo:

```sh
curl -H "Authorization: Bearer $UR_API_KEY" "https://catalogo.example/api/v1/parts/exact/?code=625994-01"
```

Un evento contiene `sequence`, `operation`, `part_id` y `part`, donde `part` es la imagen persistida **en ese evento** (campos con sufijo `_id` para catálogos). Los decimales se entregan como cadenas para conservar precisión; `null` representa ausencia y `"0"` representa cero. Las operaciones son `create`, `update`, `deactivate` y `reactivate`.

## Piezas pendientes de aprobación (campo técnico `is_sample`)

Universo Ramos presenta esta clasificación como una pieza nueva pendiente de aprobación para producción regular. El nombre técnico del campo y la política de acceso se conservan para las aplicaciones consumidoras, incluido Helians.

Cada pieza y evento entrega `is_sample` como booleano. Los eventos anteriores a esta función se entregan con `is_sample=false`. El código original no incluye la etiqueta visual `(PENDIENTE DE APROBACIÓN)`. Una pieza de muestra está pendiente de autorización; `active` sigue representando su disponibilidad y es independiente de esta clasificación.

Un administrador controla **Permitir pendientes de aprobación** en la pantalla **Integraciones** y pulsa **Guardar** para cada app. La política se asocia a su credencial; use una credencial por aplicación. Las credenciales existentes conservan el acceso a ambos tipos y las nuevas permiten elegirlo al crearlas.

La API aplica esta restricción en `/parts/`, `/parts/exact/` y `/parts/{uuid}/`, aunque se solicite `is_sample=true`. Una muestra no autorizada devuelve 404 en la consulta por UUID. El parámetro opcional `?is_sample=false` puede restringir más la selección, pero nunca ampliar los permisos de la credencial.

El flujo `/changes/` conserva las secuencias para sincronizar las bajas. Cuando una pieza es una muestra no autorizada, devuelve un marcador `excluded=true`, operación `deactivate` y una imagen mínima con UUID, `is_sample=true`, `active=false` y versión, sin código ni datos de la muestra. El consumidor debe retirar esa pieza de su catálogo local. Los eventos accesibles tienen `excluded=false` y conservan la imagen histórica habitual. Tampoco se exponen imágenes anteriores de una pieza actualmente clasificada como muestra no autorizada.

Cada cambio real de permiso incrementa `policy_version`. Los cursores nuevos están firmados y asociados a la credencial y versión de permiso. Un cursor de otra app se rechaza con 400. Al cambiar el permiso, el cursor anterior devuelve **409** con `code=resync_required`: la app debe reconstruir su catálogo desde `/bootstrap/`, eliminando las piezas excluidas y recuperando las que vuelvan a estar permitidas. No basta con añadir nuevas filas sobre la caché anterior.

`/bootstrap/` devuelve `include_samples`, `policy_version`, `parts_url` y `changes_cursor`. Use `parts_url` tal como se entrega; conserva la versión de política durante la paginación y también devuelve 409 si cambia mientras se descarga. Los cursores antiguos de solo secuencia siguen funcionando mientras no cambie la política inicial de la credencial.

El consumidor de ejemplo procesa los marcadores y el 409, reconstruye su caché de forma transaccional y permite una restricción local adicional con `UR_INCLUDE_SAMPLES=false`. El cambio de permiso no puede modificar una caché desconectada: las aplicaciones con copias propias deben implementar este protocolo y actualizarse en su siguiente sincronización. Los datos históricos de órdenes y documentos permanecen en sus apps.

La pieza también entrega `reference_customer` y `reference_plant`, que conservan las columnas adicionales del Excel sin imponer una relación de negocio. Si `PARED` contiene texto como `NO`, `wall` es `null` y `wall_note` conserva el texto original. El catálogo web tiene una **Vista Excel** con todas las columnas.

## Carga inicial sin huecos

1. Solicite `/bootstrap/` y guarde su `changes_cursor` inicial (corresponde al inicio de la secuencia).
2. Recorra todas las páginas de `parts_url`, incluyendo inactivas, y reconstruya el catálogo local por UUID central.
3. Recorra `/changes/` desde ese cursor hasta `has_more=false`. Retire las piezas con `excluded=true` y haga UPSERT por UUID con la imagen de los demás eventos. Guarde `next_cursor` en la **misma transacción local**.
4. En ejecuciones posteriores, repita el paso 3 desde el cursor guardado. Repetir una página es seguro si el consumidor hace UPSERT idempotente.

El cursor es opaco y firmado. El servidor asigna secuencias dentro de la transacción de la pieza y serializa escritores en PostgreSQL; un cursor no supera un evento anterior aún sin confirmar. La reproducción completa desde el inicio corrige también saltos posibles durante la paginación de la carga inicial. Conserve el histórico de cambios mientras existan consumidores que puedan necesitar esa reproducción.
