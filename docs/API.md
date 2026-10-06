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

La pieza también entrega `reference_customer` y `reference_plant`, que conservan las columnas adicionales del Excel sin imponer una relación de negocio. Si `PARED` contiene texto como `NO`, `wall` es `null` y `wall_note` conserva el texto original. El catálogo web tiene una **Vista Excel** con todas las columnas.

## Carga inicial sin huecos

1. Solicite `/bootstrap/` y guarde su `changes_cursor` inicial (corresponde al inicio de la secuencia).
2. Recorra todas las páginas de `/parts/`, incluyendo inactivas, y haga UPSERT por UUID central.
3. Recorra `/changes/` desde ese cursor hasta `has_more=false`. Haga UPSERT por UUID con la imagen de cada evento y guarde `next_cursor` en la **misma transacción local**.
4. En ejecuciones posteriores, repita el paso 3 desde el cursor guardado. Repetir una página es seguro si el consumidor hace UPSERT idempotente.

El cursor es opaco y firmado. El servidor asigna secuencias dentro de la transacción de la pieza y serializa escritores en PostgreSQL; un cursor no supera un evento anterior aún sin confirmar. La reproducción completa desde el inicio corrige también saltos posibles durante la paginación de la carga inicial. Conserve el histórico de cambios mientras existan consumidores que puedan necesitar esa reproducción.
