# Flujo del proyecto · Sistema de Rutas (Grafos · ED2)

> Cómo se mueve la información entre el **frontend** (navegador) y el
> **backend** (Flask), cómo cada endpoint **recibe** la petición y qué hace
> con ella, con **referencias a las líneas de código** reales del proyecto.

---

## 1. Vista general: arquitectura MVC

El proyecto es una app **Flask** organizada en capas (patrón MVC). Cada capa
solo conoce a la de abajo: la Vista pide datos al Controlador, el Controlador
delega en el Servicio, el Servicio usa el Modelo. El Modelo no sabe nada de
Flask ni del disco.

```
NAVEGADOR (Vista cliente)                      SERVIDOR (Flask)
┌─────────────────────────┐                   ┌──────────────────────────────┐
│ index.html / resultado  │   HTTP (fetch /   │ CONTROLADOR                  │
│ app.js  · map.js        │ ───form POST)──▶  │  main_controller (HTML)      │
│ MapLibre GL + Bootstrap │                   │  api_controller  (JSON /api) │
│                         │ ◀──JSON / HTML──  │            │                 │
└─────────────────────────┘                   │            ▼                 │
                                              │ SERVICIO                     │
                                              │  MapaService                 │
                                              │  RoutingService (OSRM)       │
                                              │            │                 │
                                              │            ▼                 │
                                              │ MODELO                       │
                                              │  Grafo (BFS/DFS/Dijkstra)    │
                                              │  Coordenada                  │
                                              └──────────────────────────────┘
```

| Capa | Carpeta / archivo | Rol |
|------|-------------------|-----|
| **Modelo** | `app/models/grafo.py`, `app/models/geo.py` | Datos del dominio y algoritmos de grafos |
| **Servicio** | `app/services/mapa_service.py`, `app/services/routing_service.py` | Persistencia, datos de ejemplo, enrutamiento vial |
| **Controlador** | `app/controllers/main_controller.py`, `app/controllers/api_controller.py` | Reciben la petición HTTP, validan y responden |
| **Vista** | `app/templates/*.html`, `app/static/js/*.js`, `app/static/css/*` | HTML, lógica de interfaz, mapa |
| **Arranque** | `run.py`, `app/__init__.py`, `config.py` | Crean y configuran la app |

---

## 2. Arranque de la aplicación

1. **`run.py`** crea la app con el *application factory* y la levanta en el
   puerto `5057` (`run.py:12`, `run.py:15`).
2. **`app/__init__.py` · `create_app()`** (`app/__init__.py:23`):
   - Carga la configuración (`app/__init__.py:25`).
   - Crea el **servicio del mapa** compartido por toda la app y le **inyecta**
     el enrutamiento vial OSRM leído del entorno
     (`app/__init__.py:30-33`). Queda accesible como
     `current_app.servicio_mapa`.
   - Registra los dos **Blueprints** (controladores):
     `main_bp` (sin prefijo) y `api_bp` (prefijo `/api`)
     (`app/__init__.py:36-40`).
   - Registra manejadores de error 404 y 500 que responden JSON
     (`app/__init__.py:46-53`).
3. **`config.py`** define la `Config`: clave secreta, archivo de persistencia
   `mapa.json`, parámetros del mapa (centro, zoom, estilo) y del enrutamiento
   (OSRM). La clave de MapTiler se lee **solo del entorno**, nunca del código
   (`config.py:30`, `config.py:43-48`).

---

## 3. Las dos puertas de entrada (Blueprints)

### 3.1 `main_bp` — Vistas HTML (`main_controller.py`)

| Ruta | Método | Función | Línea | Devuelve |
|------|--------|---------|-------|----------|
| `/` | GET | `index()` | `main_controller.py:17` | `index.html` con la lista de ciudades |
| `/ruta` | POST | `calcular_ruta()` | `main_controller.py:23` | `resultado.html` con la ruta calculada |

### 3.2 `api_bp` — API JSON, prefijo `/api` (`api_controller.py`)

| Ruta | Método | Función | Línea |
|------|--------|---------|-------|
| `/api/data` | GET | `api_data` | `api_controller.py:29` |
| `/api/map-config` | GET | `api_map_config` | `api_controller.py:61` |
| `/api/geojson` | GET | `api_geojson` | `api_controller.py:92` |
| `/api/todas-rutas` | POST | `api_todas_rutas` (DFS) | `api_controller.py:101` |
| `/api/matriz` | GET | `api_matriz` | `api_controller.py:132` |
| `/api/comparar` | POST | `api_comparar` | `api_controller.py:145` |
| `/api/ciudades` | GET/POST | `gestionar_ciudades` | `api_controller.py:204` |
| `/api/eliminar-ciudad` | POST | `eliminar_ciudad` | `api_controller.py:256` |
| `/api/ciudad/<nombre>` | GET | `obtener_ciudad` | `api_controller.py:283` |
| `/api/rutas` | GET/POST | `gestionar_rutas` | `api_controller.py:312` |
| `/api/eliminar-carretera` | POST | `eliminar_carretera` | `api_controller.py:381` |
| `/api/estadisticas` | GET | `obtener_estadisticas` | `api_controller.py:419` |
| `/api/reset` | POST | `reset_grafo` | `api_controller.py:427` |

Todos los endpoints API obtienen el servicio con el *helper* `_servicio()`
(`api_controller.py:17`) y arman errores uniformes con `_error()`
(`api_controller.py:21`).

---

## 4. Cómo recibe cada método la petición

El backend recibe los datos por **tres vías** distintas según el endpoint:

| Vía | Cómo se lee en Flask | Quién la usa |
|-----|----------------------|--------------|
| **Formulario** (`application/x-www-form-urlencoded`) | `request.form.get(...)` | `/ruta` (`main_controller.py:27-30`) |
| **Cuerpo JSON** (`application/json`) | `request.json` | Todos los POST de `/api` (p. ej. `api_controller.py:106`, `:211`, `:319`) |
| **Query string** (`?clave=valor`) | `request.args.get(...)` | `/api/matriz` (`api_controller.py:136`) |

### 4.1 Petición por **formulario** — calcular una ruta

`index.html` tiene un `<form method="post">` que apunta a `main.calcular_ruta`
(`index.html:27`). Sus campos `origen`, `destino`, `algoritmo` y `criterio`
(`index.html:30-53`) viajan como formulario. En el backend:

```python
# main_controller.py:27-30
origen   = request.form.get("origen", "").strip()
destino  = request.form.get("destino", "").strip()
criterio = request.form.get("criterio", "distancia")
algoritmo = request.form.get("algoritmo", "dijkstra")
```

Según el algoritmo elegido llama a `grafo.bfs(...)` o `grafo.dijkstra(...)`
(`main_controller.py:52-59`), calcula el detalle por tramos
(`main_controller.py:65-69`) y renderiza `resultado.html` con los datos o un
mensaje de error.

### 4.2 Petición por **JSON** — alta de ciudad (ejemplo de POST)

El frontend envía JSON con el *helper* `postJSON` (`app.js:21`):

```js
// app.js:21-27
return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
}).then(r => r.json());
```

`agregarCiudad()` (`app.js:49`) recoge el formulario del modal y llama
`postJSON('/api/ciudades', data)` (`app.js:52`). En el backend, la rama POST
de `gestionar_ciudades` (`api_controller.py:209`):

```python
# api_controller.py:211-229
data   = request.json or {}
nombre = data.get("nombre", "").strip()
...
coordenada = None
lat, lon = data.get("lat"), data.get("lon")
if lat not in (None, "") and lon not in (None, ""):
    coordenada = Coordenada(lat, lon)   # valida rangos en el modelo
grafo.agregar_ciudad(nombre, data.get("tipo", "normal"), coordenada)
servicio.guardar()
```

### 4.3 Petición por **query string** — matriz de adyacencia

`mostrarMatriz()` pide `GET /api/matriz?criterio=...` (`app.js:175`). El
backend lo lee de `request.args` y lo valida contra una lista blanca
(`api_controller.py:136-138`).

---

## 5. Recorrido completo de tres operaciones típicas

### 5.1 Cargar la página y dibujar el mapa

```
Navegador                         Flask                         Servicio/Modelo
   │ GET /                          │                                  │
   │ ─────────────────────────────▶│ index() main_controller.py:17    │
   │                               │ grafo.obtener_ciudades()──────────▶ grafo.py:84
   │ ◀── index.html (lista) ───────│                                  │
   │                               │                                  │
   │ DOMContentLoaded:             │                                  │
   │  iniciarMapa()  map.js:53     │                                  │
   │ GET /api/map-config ─────────▶│ api_map_config :61               │
   │ ◀── {center,zoom,hasKey} ─────│                                  │
   │ GET /api/geojson ────────────▶│ api_geojson :92 ──▶ servicio.geojson() mapa_service.py:277
   │ ◀── {ciudades,carreteras,routing}                                │
   │  dibujarCiudades/Carreteras   │                                  │
   │ GET /api/estadisticas ───────▶│ obtener_estadisticas :419        │
   │ ◀── {total_ciudades,...} ─────│  (app.js:218 rellena las tarjetas)
```

- **`iniciarMapa()`** (`map.js:53`) pide `/api/map-config`; si hay clave de
  MapTiler usa su estilo, si no, el mapa base OSM de `estiloOSM()`
  (`map.js:30`). Al cargar, dispara `cargarDatosGeo` (`map.js:69`).
- **`cargarDatosGeo()`** (`map.js:74`) pide `/api/geojson` y llama a
  `dibujarCarreteras` (`map.js:134`), `dibujarCiudades` (`map.js:181`),
  `ajustarVista` (`map.js:248`) y `avisarTrazadoVial` (`map.js:95`).
- Cada ciudad se dibuja como **punto** (capa `ciudades-punto`, `map.js:185`)
  más su **nombre** (capa de texto `ciudades-texto`, `map.js:212`). El color
  depende del tipo (`COLORES_TIPO`, `map.js:17`).
- El backend arma el GeoJSON en `MapaService.geojson()`
  (`mapa_service.py:277`): recorre ciudades con coordenada
  (`mapa_service.py:290-307`) y carreteras (`mapa_service.py:314-357`),
  añadiendo el bloque `routing` con el estado del enrutamiento
  (`mapa_service.py:371-376`).

### 5.2 Calcular una ruta (Dijkstra / BFS)

```
Navegador                         Flask                         Modelo
   │ submit <form> POST /ruta ────▶│ calcular_ruta :23                │
   │  (origen,destino,algoritmo,   │ request.form.get(...) :27-30     │
   │   criterio)                   │ grafo.dijkstra/bfs ──────────────▶ grafo.py:135 / :185
   │                               │ grafo.detalle_camino :272        │
   │ ◀── resultado.html ───────────│ render_template :70              │
   │  map.js resalta rutaCamino    │                                  │
```

- En `resultado.html` se inyecta el camino calculado a una variable global
  `rutaCamino` (`resultado.html:110`), que `map.js` lee en `cargarDatosGeo`
  (`map.js:85`) y resalta con `resaltarRuta()` (`map.js:259`).
- **Dijkstra** (`grafo.py:135`) usa una cola de prioridad (`heapq`) y el
  índice de costo según el criterio (`grafo.py:145`, `INDICES_COSTO`
  `grafo.py:25`).
- **BFS** (`grafo.py:185`) busca el camino con menos paradas usando una cola
  (`deque`), ignorando los pesos.

### 5.3 Agregar una ciudad con clic en el mapa

```
Navegador                                           Flask
   │ botón "Nueva ciudad" → elegirEnMapa(true) map.js:310
   │   activa modoSeleccion, cursor crosshair
   │ clic en el mapa → fijarUbicacion(lngLat) map.js:328
   │   rellena #ciudadLat/#ciudadLon, pone marcador, abre modal
   │ "Agregar" → agregarCiudad() app.js:49
   │ POST /api/ciudades (JSON) ───────────────▶ gestionar_ciudades :204 (POST :209)
   │                                            Coordenada(lat,lon) valida geo.py:34
   │                                            grafo.agregar_ciudad :45
   │                                            servicio.guardar() mapa_service.py:177
   │ ◀── {mensaje,total_ciudades} ─────────────│
   │  toast + location.reload() app.js:54-55
```

---

## 6. Capa Servicio en detalle

### 6.1 `MapaService` (`mapa_service.py`)

- **Constructor** (`mapa_service.py:43`): guarda la ruta del archivo, recibe el
  `RoutingService`, carga la caché de rutas viales y llama a `inicializar()`.
- **`inicializar()`** (`mapa_service.py:185`): si existe `mapa.json` lo carga;
  si no, siembra el ejemplo con `seed_default()` (`mapa_service.py:59`), que
  crea los 9 departamentos de Bolivia con sus coordenadas reales
  (`COORDENADAS_DEPARTAMENTOS`, `mapa_service.py:29`) y 12 carreteras
  (`mapa_service.py:82-97`).
- **`serializar()` / `guardar()`** (`mapa_service.py:102`, `:177`): vuelcan el
  grafo a `mapa.json` (sin duplicar aristas).
- **`geojson()`** (`mapa_service.py:277`): produce el `FeatureCollection` de
  ciudades y carreteras para el mapa, integrando la geometría vial.
- **`estadisticas()`** (`mapa_service.py:382`): promedios para las tarjetas del
  panel.

### 6.2 `RoutingService` — enrutamiento vial OSRM (`routing_service.py`)

- Traza las carreteras **siguiendo la red vial real** en vez de líneas rectas.
  Se usa OSRM (sin clave) porque la API de routing de MapTiler está en beta
  cerrada (explicado en `routing_service.py:8-13`).
- **`desde_config()`** (`routing_service.py:45`) lo construye desde la
  configuración de Flask.
- **`ruta_vial()`** (`routing_service.py:69`) consulta OSRM y **nunca lanza
  excepciones de red**: devuelve siempre un dict con `estado`
  (`ok` / `sin_ruta` / `error_red` / `deshabilitado`, `routing_service.py:79-83`).
- En `MapaService._geometria_vial()` (`mapa_service.py:243`) se aplica una
  **caché** (evita reconsultar) y un **corte de circuito**: si OSRM no
  responde (`error_red`), se marca `estado["caido"]` (`mapa_service.py:269`)
  para no encadenar timeouts. Las claves de caché son estables por par de
  ciudades y coordenadas (`_clave_ruta`, `mapa_service.py:230`).

---

## 7. Capa Modelo en detalle

### 7.1 `Grafo` (`grafo.py`) — lista de adyacencia

Cada arista guarda tres costos: distancia (km), tiempo (min), peaje (Bs). El
índice de cada costo está en `INDICES_COSTO` (`grafo.py:25`).

| Operación | Método | Línea |
|-----------|--------|-------|
| Agregar carretera (bidireccional) | `agregar_arista` | `grafo.py:35` |
| Agregar ciudad (con coordenada opcional) | `agregar_ciudad` | `grafo.py:45` |
| Eliminar ciudad y sus aristas | `eliminar_ciudad` | `grafo.py:58` |
| Eliminar una carretera | `eliminar_arista` | `grafo.py:70` |
| **Dijkstra** (menor costo) | `dijkstra` | `grafo.py:135` |
| **BFS** (menos paradas) | `bfs` | `grafo.py:185` |
| **DFS** (todas las rutas simples) | `dfs_todas_rutas` | `grafo.py:213` |
| Detalle por tramos | `detalle_camino` | `grafo.py:272` |
| **Matriz de adyacencia** | `obtener_matriz_adyacencia` | `grafo.py:293` |

- **DFS con backtracking** (`grafo.py:226-241`): explora con `_dfs` recursivo,
  marca/desmarca visitados y limita la explosión combinatoria con
  `max_rutas=300` (`grafo.py:213`, `:227`).

### 7.2 `Coordenada` (`geo.py`) — *value object* georreferenciado

- **`validar()`** (`geo.py:34`): convierte a `float` y verifica rangos
  geográficos; lanza `ValueError` si algo no es válido (`geo.py:45-56`).
- **`to_geojson()`** (`geo.py:73`): devuelve la posición en orden GeoJSON
  `[lon, lat]` (clave para que el mapa la dibuje bien).
- **`en_bolivia()`** (`geo.py:59`): valida la caja envolvente del país.

---

## 8. Capa Vista (frontend) en detalle

### 8.1 Plantillas (Jinja2)

- **`base.html`**: plantilla madre. Carga Bootstrap, MapLibre GL JS
  (`base.html:13-15`), el sprite de iconos SVG (`base.html:18-34`) y define los
  bloques `content` y `scripts`.
- **`index.html`**: tablero principal. Formulario de cálculo de ruta
  (`index.html:27-66`), panel del mapa (`index.html:87-95`), tarjetas de
  estadísticas (`index.html:99-116`) y los modales de gestión de ciudades y
  carreteras (`index.html:141-313`). Carga `map.js` y `app.js`
  (`index.html:320-321`).
- **`resultado.html`**: muestra la ruta calculada (origen→destino, métricas,
  tabla por tramo) y el mapa con la ruta resaltada. Pasa el camino a JS en
  `rutaCamino` (`resultado.html:110`).

### 8.2 JavaScript

**`app.js`** — lógica de la interfaz principal:

| Función | Qué hace | Línea |
|---------|----------|-------|
| `mostrarModal` / `cerrarModal` | abren/cierran modales Bootstrap | `app.js:6` / `:10` |
| `postJSON` | POST con cuerpo JSON | `app.js:21` |
| `toast` | notificaciones flotantes | `app.js:29` |
| `agregarCiudad` | POST `/api/ciudades` | `app.js:49` |
| `eliminarCiudad` | POST `/api/eliminar-ciudad` | `app.js:59` |
| `agregarRuta` | POST `/api/rutas` | `app.js:69` |
| `eliminarRuta` | POST `/api/eliminar-carretera` | `app.js:82` |
| `restaurarEjemplo` | POST `/api/reset` | `app.js:93` |
| `listarRutas` / `listarCiudades` | GET y tabla | `app.js:103` / `:116` |
| `calcularDFS` | POST `/api/todas-rutas` | `app.js:126` |
| `compararAlgoritmos` | POST `/api/comparar` | `app.js:148` |
| `mostrarMatriz` | GET `/api/matriz?criterio=` | `app.js:172` |
| `mostrarCiudadEnModal` | detalle de ciudad en modal | `app.js:192` |
| init `DOMContentLoaded` | carga estadísticas | `app.js:216` |

**`map.js`** — mapa con MapLibre GL JS:

| Función | Qué hace | Línea |
|---------|----------|-------|
| `estiloOSM` | estilo base OSM de respaldo | `map.js:30` |
| `iniciarMapa` | crea el mapa con `/api/map-config` | `map.js:53` |
| `cargarDatosGeo` | pide `/api/geojson` y dibuja | `map.js:74` |
| `avisarTrazadoVial` | avisa si una carretera no es vial | `map.js:95` |
| `dibujarCarreteras` | capas de líneas y etiquetas | `map.js:134` |
| `dibujarCiudades` | capas de puntos, texto e interacción | `map.js:181` |
| `resaltarRuta` | resalta la ruta calculada | `map.js:259` |
| `mostrarInfoCiudad` | popup/modal al hacer clic | `map.js:282` |
| `elegirEnMapa` | activa el modo "clic para ubicar" | `map.js:310` |
| `fijarUbicacion` | fija coordenadas y abre el modal | `map.js:328` |

> **Nota técnica del mapa**: las capas de texto (symbol) necesitan glifos
> válidos. El servidor de glifos se fija en `estiloOSM()` (`map.js:37`) y cada
> capa de texto usa **una sola fuente** (`map.js:171`, `:221`); si se mezclara
> una fuente inexistente, el *tile* completo quedaría en estado `errored` y
> desaparecerían también los puntos de las ciudades.

---

## 9. Formato de los datos intercambiados

### 9.1 `/api/geojson` (respuesta)

```json
{
  "ciudades":   { "type": "FeatureCollection", "features": [ /* Point */ ] },
  "carreteras": { "type": "FeatureCollection", "features": [ /* LineString */ ] },
  "routing": {
    "habilitado": true,
    "perfil": "driving",
    "servicio_caido": false,
    "fallidos": []
  }
}
```

Cada carretera incluye en sus `properties` la clave `"trazado"` con valor
`"vial"` (siguió carreteras reales) o `"recta"` (línea recta de respaldo)
(`mapa_service.py:354`).

### 9.2 `/api/ciudades` (POST → request)

```json
{ "nombre": "El Alto", "tipo": "normal", "lat": -16.50, "lon": -68.15 }
```

### 9.3 `/api/comparar` (respuesta)

Lista de resultados con `algoritmo`, `camino` y los costos, comparando BFS y
Dijkstra en los tres criterios (`api_controller.py:161-196`).

---

## 10. Resumen del ciclo petición→respuesta

1. El usuario interactúa con la **Vista** (`index.html` + `app.js`/`map.js`).
2. La Vista envía la petición:
   - **formulario** → `/ruta` (`request.form`),
   - **JSON** → endpoints POST de `/api` (`request.json`),
   - **query** → `/api/matriz` (`request.args`).
3. El **Controlador** valida la entrada y arma la respuesta; nunca toca el
   disco ni implementa algoritmos (delega).
4. El **Servicio** (`MapaService`) persiste y construye el GeoJSON; el
   `RoutingService` aporta la geometría vial.
5. El **Modelo** (`Grafo`, `Coordenada`) ejecuta los algoritmos y guarda los
   datos del dominio.
6. La respuesta vuelve como **HTML** (`render_template`) o **JSON**
   (`jsonify`), y la Vista la pinta (recarga la página, dibuja en el mapa o
   abre un modal con tablas).
```
