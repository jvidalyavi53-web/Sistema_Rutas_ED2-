# Integración de Mapa Real (MapTiler + MapLibre GL JS)

Documentación de la integración del **mapa real** en el Sistema de Rutas,
siguiendo la arquitectura **MVC** sobre Flask. Sustituye al grafo abstracto
(vis-network) por un mapa geográfico real de Bolivia donde cada ciudad se
ubica en sus coordenadas reales y las carreteras se trazan entre ellas
**siguiendo la red vial real** (no en línea recta) — ver la sección 5,
*Navegación*.

---

## 1. Comparación MapTiler vs Mapbox

| Criterio | **MapTiler** | **Mapbox** |
|---|---|---|
| Integración con Flask | Muy alta: solo se sirve la URL del estilo desde una variable de entorno; cliente MapLibre GL JS (open source). | Alta, pero SDK propietario (Mapbox GL JS v2+) y token obligatorio. |
| Cumplimiento MVC | Excelente: datos en el Modelo, GeoJSON en el Servicio, endpoints en el Controlador, render en la Vista. | Viable, pero su tooling empuja lógica fuera del repo. |
| Costos | Gratis **sin tarjeta**, ~100 000 cargas/mes. | Gratis **con tarjeta**, ~50 000 cargas/mes. |
| Precisión | Buena (OpenStreetMap + fuentes propias). | Muy alta (datos premium). |
| Actualizaciones | Frecuentes (sigue a OSM). | Muy frecuentes (equipo propio). |
| Rendimiento web | Vector tiles + GPU, rápido. | Equivalente. |
| Autenticación | API key en URL + restricción por dominio. | Access token + restricción por URL. |
| Límites | 100k cargas/mes gratis. | 50k cargas/mes gratis. |

### Elección: **MapTiler**

Para un proyecto académico con Flask + MVC en Bolivia, MapTiler gana por menor
fricción y mejor encaje arquitectónico: registro **sin tarjeta**, tier gratuito
el doble de generoso, cliente **MapLibre GL JS de código abierto** (sin la
licencia propietaria de Mapbox GL JS v2+), cobertura OSM suficiente para los
departamentos de Bolivia y **restricción de la clave por dominio** para la
seguridad. Mapbox es más potente pero está sobredimensionado aquí.

---

## 2. Estructura del código según MVC

```
MODELO (datos + validación de dominio)
  app/models/geo.py        -> Coordenada: validación de lat/lon y caja de Bolivia
  app/models/grafo.py      -> Grafo.coordenadas {ciudad -> Coordenada}
                              asignar_coordenada / obtener_coordenada

SERVICIO (preparación y persistencia de datos)
  app/services/mapa_service.py
                           -> COORDENADAS_DEPARTAMENTOS (coords reales)
                              seed con coordenadas, serialización lat/lon,
                              migración por nombre, geojson()
                              trazado vial (OSRM) + caché en disco
  app/services/routing_service.py
                           -> RoutingService: cliente OSRM (enrutamiento vial)
                              ruta_vial() -> geometría que sigue carreteras

CONTROLADOR (endpoints HTTP, sin lógica de negocio)
  app/controllers/api_controller.py
                           -> GET /api/map-config  (clave desde env var)
                              GET /api/geojson      (datos georreferenciados)
                              POST /api/ciudades    (acepta lat/lon validadas)

VISTA (presentación, sin lógica de negocio)
  app/templates/base.html  -> carga MapLibre GL JS (CSS + JS)
  app/templates/index.html -> contenedor #map + campos lat/lon
  app/templates/resultado.html -> #map con la ruta resaltada
  app/static/js/map.js     -> render del mapa, marcadores, rutas, popups,
                              aviso de trazado no vial (avisarTrazadoVial)
  app/static/css/style.css -> estilos de #map, popups y .map-aviso
```

**Separación de responsabilidades:**
- La **validación de coordenadas** (rangos geográficos) vive en el Modelo
  (`Coordenada`), no en la Vista ni en el Controlador.
- El **armado del GeoJSON** vive en el Servicio (`geojson()`), no en la Vista.
- El **Controlador** solo lee la entrada, delega y responde JSON.
- La **Vista** (`map.js`) solo dibuja lo que recibe; no calcula rutas ni costos.

---

## 3. Configurar la clave API (seguridad)

La clave **nunca** está escrita en el código ni en las plantillas. Se lee de la
variable de entorno `MAPTILER_API_KEY` y se entrega al cliente vía el endpoint
`GET /api/map-config`.

**Pasos:**

1. Crea una cuenta gratis en https://cloud.maptiler.com/ y copia tu clave en
   https://cloud.maptiler.com/account/keys/
2. En el panel de MapTiler, **restringe la clave por dominio** (*Allowed
   origins*): añade `http://localhost:5057` para desarrollo y tu dominio real
   en producción. Así la clave no sirve desde otros sitios.
3. Copia el archivo de ejemplo y pega tu clave:
   ```powershell
   Copy-Item .env.example .env
   # edita .env y coloca:  MAPTILER_API_KEY=tu_clave_aqui
   ```
4. (Opcional) Instala python-dotenv para que Flask lea el `.env`:
   ```powershell
   py -m pip install python-dotenv
   ```
   Alternativa sin `.env`: definir la variable en la sesión:
   ```powershell
   $env:MAPTILER_API_KEY = "tu_clave_aqui"
   ```
5. Arranca: `py run.py` (o el preview en el puerto 5057).

> El archivo `.env` está en `.gitignore`: **no se versiona**.
>
> **Nota de seguridad:** en cualquier mapa de cliente la clave viaja al
> navegador en las peticiones de *tiles* (es inevitable). La protección real es
> la **restricción por dominio** del paso 2. Por eso `/api/map-config` solo
> entrega la URL del estilo cuando hay clave; sin clave, el frontend usa un mapa
> base de OpenStreetMap como respaldo de desarrollo.

---

## 4. Funcionalidades del mapa

- **Mapa base real** de Bolivia (MapTiler con clave; OpenStreetMap sin clave).
- **Ciudades** como puntos coloreados por tipo (capital, normal, turística,
  comercial, industrial) con su nombre como etiqueta.
- **Carreteras** como líneas entre ciudades, etiquetadas con la distancia.
- **Clic en una ciudad**: muestra su detalle (tipo, conexiones, rutas). En la
  página principal abre el modal; en la de resultado, un popup sobre el mapa.
- **Ruta resaltada**: en `resultado.html` la ruta calculada (Dijkstra/BFS) se
  pinta en rosa sobre las carreteras y ciudades del camino.
- **Alta de ciudad georreferenciada**: el modal acepta latitud/longitud, o el
  botón "Elegir ubicación en el mapa" permite fijarla con un clic.
- **Responsivo**: el contenedor `#map` se adapta a escritorio y móvil; el mapa
  se reajusta (`map.resize()`) al cambiar el tamaño de la ventana.
- **Controles**: zoom/rotación (NavigationControl) y atribución.

---

## 5. Navegación: trazado por carreteras reales

El recorrido entre dos ciudades **sigue estrictamente las carreteras** del mapa
en lugar de unir los puntos con una línea recta.

### 5.1 ¿Por qué no la API de rutas de MapTiler?

MapTiler Cloud ofrece mapas, *tiles*, geocoding y elevación, pero su **API de
enrutamiento (Directions) está en *beta cerrada***: requiere solicitar acceso
por formulario y **no funciona con una clave gratuita estándar**. Por eso el
enrutamiento se resuelve con **OSRM** (Open Source Routing Machine), que expone
un servidor público de demostración **sin clave** y devuelve la geometría de la
ruta en GeoJSON respetando el perfil de transporte.

> La clave de MapTiler sigue siendo correcta y válida para el **mapa base**
> (sección 3); solo el *enrutamiento* usa otro proveedor.

### 5.2 Cómo funciona (Servicio → Vista)

1. **`RoutingService`** (`app/services/routing_service.py`) es el cliente OSRM.
   `ruta_vial(origen, destino)` arma la URL
   `/route/v1/{perfil}/{lon1},{lat1};{lon2},{lat2}?overview=simplified&geometries=geojson`
   y devuelve **siempre** un dict de estado, nunca lanza excepciones de red:
   - `{"estado": "ok", "coordinates": [[lon,lat], ...], "distancia_m", "duracion_s"}`
   - `{"estado": "sin_ruta"}` — no existe ruta vial entre A y B.
   - `{"estado": "error_red"}` — OSRM no respondió / fallo de red.
   - `{"estado": "deshabilitado"}` — enrutamiento apagado por configuración.
2. **`MapaService.geojson()`** pide a OSRM la geometría de cada carretera y
   sustituye la línea recta por el conjunto de coordenadas de la **red vial
   oficial** (`"trazado": "vial"`). El perfil (`driving`) hace que la ruta
   respete las vías.
3. **`map.js`** dibuja la `LineString` resultante: como trae decenas de puntos
   que siguen las curvas de la carretera, el render mantiene **visibilidad y
   fluidez** del trazado.

### 5.3 Caché en disco y *circuit breaker*

- Las geometrías viales se **cachean** en `<mapa>_rutas_viales.json` (ignorado
  por git). La primera carga consulta OSRM (varios segundos para todo el grafo);
  las siguientes leen del disco (milisegundos), muy por debajo de los 3 s.
- Si OSRM **no responde**, el servicio marca `servicio_caido` y deja de
  reintentar en esa misma construcción del GeoJSON (evita encadenar 12 *timeouts*
  y degradar el tiempo de respuesta). Distinguir `sin_ruta` de `error_red`
  permite **cachear los "sin ruta"** y no reconsultarlos.

### 5.4 Manejo de errores para el usuario

Cuando alguna carretera no se pudo trazar por vías reales, la meta `routing`
del GeoJSON lo informa y la Vista muestra un **aviso**:

- `servicio_caido = true` → *"No se pudo conectar al servicio de rutas viales:
  algunas carreteras se muestran como línea recta."*
- `fallidos = [...]` → *"Sin ruta vial disponible para N carretera(s): ...
  Se muestran como línea recta."*

El aviso aparece como *toast* en la página principal (si existe `toast`) o como
banner `.map-aviso` sobre el mapa en `resultado.html`. En todos los casos el
mapa **sigue funcionando** con el respaldo de línea recta; nunca se rompe.

### 5.5 Configuración (variables de entorno)

| Variable | Defecto | Para qué |
|---|---|---|
| `ROUTING_HABILITADO` | `true` | Activa/desactiva el trazado vial. |
| `OSRM_URL` | `https://router.project-osrm.org` | Servidor OSRM. |
| `ROUTING_PERFIL` | `driving` | Perfil de transporte (respeta las vías). |
| `ROUTING_TIMEOUT` | `8` | Segundos máximos por consulta a OSRM. |

Se leen en `config.py` y `RoutingService.desde_config(app.config)` las inyecta
al servicio en `app/__init__.py`. **No requiere clave.**

---

## 6. Pruebas funcionales

Prueba de humo de los endpoints (modelo + servicio + controlador) con
`test_client`, sin tocar el `mapa.json` real (usa un archivo temporal):

```powershell
py _smoke_geo.py       # prueba hermética: SIN red (ROUTING_HABILITADO=false).
                       # valida coords, map-config, geojson, alta con/sin
                       # coords, persistencia y que sin routing la carretera
                       # sea recta (2 puntos) y meta routing deshabilitada.

py _smoke_routing.py   # prueba en vivo: REQUIERE INTERNET (OSRM).
                       # verifica que las carreteras sigan vías reales (no
                       # recta) en escenarios urbano, interurbano y con
                       # obstáculos geográficos; que la distancia vial > recta;
                       # el manejo de error (servicio caído -> error_red /
                       # respaldo recto) y la creación de la caché en disco.
```

Verificación en navegador (preview, puerto 5057): el mapa carga sin errores de
consola, instancia el canvas de MapLibre, dibuja las 9 ciudades y 12 carreteras
de Bolivia con su **trazado vial** (cada carretera sigue las carreteras reales,
no una línea recta) y resalta la ruta en la página de resultado. Con la caché
caliente el GeoJSON responde en milisegundos, muy por debajo de 3 s.

Estilo Python: `pycodestyle --max-line-length=79` sin advertencias.
