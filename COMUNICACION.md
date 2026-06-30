# Comunicación Backend ↔ Frontend — Sistema de Rutas

Este documento explica **cómo se comunican el frontend (navegador) y el backend
(Flask)** en el proyecto: qué endpoint expone el servidor, con qué **método HTTP**
se llama, **qué función del frontend** lo invoca, **qué función del backend** lo
atiende y **en qué líneas de código** está cada una.

> Las referencias de línea (`archivo:L10-L20`) corresponden a la versión actual
> del código. Si editas un archivo, las líneas pueden desplazarse; el **nombre de
> la función** siempre es la referencia más estable.

---

## 1. Arquitectura en capas (MVC)

Cada petición recorre las mismas capas. La lógica nunca se mezcla:

```
NAVEGADOR (Vista JS)                SERVIDOR FLASK
─────────────────────              ───────────────────────────────────────────
index.html / resultado.html        CONTROLADOR        SERVICIO        MODELO
  static/js/app.js        ──HTTP──▶ controllers/  ───▶ services/  ───▶ models/
  static/js/map.js        ◀─JSON── api_controller    mapa_service    grafo.py
  (MapLibre GL JS)                 main_controller    (persistencia)  geo.py
```

- **Vista** (`app/templates/*.html`, `app/static/js/*.js`): dibuja la interfaz y
  hace las peticiones con `fetch(...)` o con el envío de un `<form>`.
- **Controlador** (`app/controllers/*.py`): recibe la petición, **valida** la
  entrada y arma la respuesta (JSON o HTML). No contiene algoritmos.
- **Servicio** (`app/services/mapa_service.py`): persistencia en `mapa.json`,
  datos de ejemplo, estadísticas y armado del **GeoJSON** del mapa real.
- **Modelo** (`app/models/grafo.py` + `app/models/geo.py`): la clase `Grafo`
  con los algoritmos (BFS, DFS, Dijkstra, matriz) y la clase `Coordenada`
  (validación de latitud/longitud).

**Dos tipos de respuesta del backend:**

| Tipo | Controlador | Devuelve | Lo consume |
|------|-------------|----------|------------|
| **Vistas HTML** | `main_controller.py` | una página renderizada (`render_template`) | el navegador (recarga de página) |
| **API JSON** | `api_controller.py` (prefijo `/api`) | datos en JSON (`jsonify`) | el JavaScript con `fetch` |

---

## 2. Tabla resumen de endpoints

| # | Método | Endpoint | Llama (frontend) | Atiende (backend) |
|---|--------|----------|------------------|-------------------|
| 1 | GET | `/` | carga inicial del navegador | `index()` · `main_controller.py:L16-L19` |
| 2 | POST | `/ruta` | `<form>` · `index.html:L27` | `calcular_ruta()` · `main_controller.py:L22-L62` |
| 3 | GET | `/api/map-config` | `iniciarMapa()` · `map.js:L51-L70` | `api_map_config()` · `api_controller.py:L57-L83` |
| 4 | GET | `/api/geojson` | `cargarDatosGeo()` · `map.js:L72-L87` | `api_geojson()` · `api_controller.py:L86-L89` |
| 5 | POST | `/api/todas-rutas` | `calcularDFS()` · `app.js:L126-L145` | `api_todas_rutas()` · `api_controller.py:L95-L119` |
| 6 | GET | `/api/matriz` | `mostrarMatriz()` · `app.js:L172-L189` | `api_matriz()` · `api_controller.py:L122-L132` |
| 7 | POST | `/api/comparar` | `compararAlgoritmos()` · `app.js:L148-L169` | `api_comparar()` · `api_controller.py:L135-L181` |
| 8 | GET | `/api/ciudades` | `listarCiudades()` · `app.js:L116-L123` | `gestionar_ciudades()` · `api_controller.py:L187-L232` |
| 9 | POST | `/api/ciudades` | `agregarCiudad()` · `app.js:L49-L57` | `gestionar_ciudades()` · `api_controller.py:L187-L232` |
| 10 | POST | `/api/eliminar-ciudad` | `eliminarCiudad()` · `app.js:L59-L67` | `eliminar_ciudad()` · `api_controller.py:L235-L257` |
| 11 | GET | `/api/ciudad/<nombre>` | `mostrarInfoCiudad()` · `map.js:L236-L255` | `obtener_ciudad()` · `api_controller.py:L260-L281` |
| 12 | GET | `/api/rutas` | `listarRutas()` · `app.js:L103-L114` | `gestionar_rutas()` · `api_controller.py:L287-L348` |
| 13 | POST | `/api/rutas` | `agregarRuta()` · `app.js:L69-L80` | `gestionar_rutas()` · `api_controller.py:L287-L348` |
| 14 | POST | `/api/eliminar-carretera` | `eliminarRuta()` · `app.js:L82-L91` | `eliminar_carretera()` · `api_controller.py:L351-L383` |
| 15 | GET | `/api/estadisticas` | init `DOMContentLoaded` · `app.js:L216-L224` | `obtener_estadisticas()` · `api_controller.py:L389-L394` |
| 16 | POST | `/api/reset` | `restaurarEjemplo()` · `app.js:L93-L100` | `reset_grafo()` · `api_controller.py:L397-L411` |

> El endpoint heredado `GET /api/data` (`api_data()` · `api_controller.py:L28-L51`)
> sigue disponible (nodos/aristas del antiguo grafo vis-network) pero **ya no lo
> consume el frontend**: el mapa real usa `/api/geojson`.

---

## 3. Detalle de cada endpoint

### 3.1 Vistas HTML (`main_controller.py`)

#### 1) `GET /` — Página principal
- **Backend:** `index()` — `app/controllers/main_controller.py:L16-L19`
- **Frontend:** no lo llama ningún JS; es la **carga inicial** de la página.
- **Qué hace:** obtiene la lista de ciudades del grafo y renderiza
  `index.html` (que recibe la variable `ciudades` para llenar los `<select>`).
- **Respuesta:** HTML (la página completa).

#### 2) `POST /ruta` — Calcular una ruta (Dijkstra o BFS)
- **Backend:** `calcular_ruta()` — `app/controllers/main_controller.py:L22-L62`
- **Frontend:** el formulario `<form action="{{ url_for('main.calcular_ruta') }}"
  method="post">` en `app/templates/index.html:L27`. Se envía con el botón
  *Calcular ruta* (`index.html:L56`).
- **Método:** `POST` con datos de **formulario** (no JSON). El control de
  Dijkstra/BFS lo hace `toggleCriterio()` (`app.js:L15-L19`), enlazado al
  `<select id="selAlgoritmo">` (`index.html:L42`).
- **Qué envía el formulario:**
  | campo | origen en el HTML |
  |-------|-------------------|
  | `origen` | `index.html:L30` |
  | `destino` | `index.html:L36` |
  | `algoritmo` | `index.html:L42` (`dijkstra` o `bfs`) |
  | `criterio` | `index.html:L49` (`distancia` / `tiempo` / `peaje`) |
- **Qué hace en el backend:** si `algoritmo == "bfs"` llama a `grafo.bfs(...)`;
  si no, a `grafo.dijkstra(origen, destino, criterio)`. Calcula el detalle por
  tramos con `grafo.detalle_camino(...)`.
- **Respuesta:** HTML renderizado con `resultado.html` (recarga de página).
  Esa página vuelve a cargar `map.js`, que pide `/api/map-config` y `/api/geojson`
  para dibujar el mapa real y resalta la ruta con la variable `rutaCamino`
  (`resultado.html:L110`) mediante `resaltarRuta()` (`map.js:L213-L231`).

---

### 3.2 API · Mapa real (`api_controller.py`)

#### 3) `GET /api/map-config` — Configuración del mapa (clave + centro/zoom)
- **Backend:** `api_map_config()` — `api_controller.py:L57-L83`
- **Frontend:** `iniciarMapa()` — `app/static/js/map.js:L51-L70`
  (el `fetch('/api/map-config')` está en `map.js:L55`).
- **Cuándo:** al cargar **tanto** `index.html` como `resultado.html` (ambas
  incluyen `map.js`, que se ejecuta en `DOMContentLoaded`, `map.js:L290`).
- **Seguridad:** la clave de MapTiler se lee de la variable de entorno
  `MAPTILER_API_KEY` (vía `current_app.config`) y **solo** se entrega aquí, dentro
  de la `styleUrl`. Nunca está escrita en plantillas ni en los `.js` estáticos.
  Si no hay clave, `hasKey` es `false` y el cliente usa el respaldo OpenStreetMap.
- **Respuesta JSON (sin clave):**
  ```json
  { "provider": "osm", "hasKey": false, "center": [-64.9, -16.9], "zoom": 4.6 }
  ```
- **Respuesta JSON (con clave):** además incluye
  `"styleUrl": "https://api.maptiler.com/maps/streets-v2/style.json?key=..."`.

#### 4) `GET /api/geojson` — Ciudades y carreteras georreferenciadas
- **Backend:** `api_geojson()` — `api_controller.py:L86-L89`
  (delega en `MapaService.geojson()` · `mapa_service.py:L179-L247`).
- **Frontend:** `cargarDatosGeo()` — `app/static/js/map.js:L72-L87`
  (el `fetch('/api/geojson')` está en `map.js:L73`); se llama en el evento
  `map.on('load', ...)` tras crear el mapa.
- **Respuesta JSON:** dos `FeatureCollection` de GeoJSON:
  ```json
  {
    "ciudades": { "type": "FeatureCollection", "features": [
      { "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [-68.15, -16.5] },
        "properties": { "nombre": "La Paz", "tipo": "capital", "conexiones": 2 } }
    ]},
    "carreteras": { "type": "FeatureCollection", "features": [
      { "type": "Feature",
        "geometry": { "type": "LineString",
                      "coordinates": [[-68.15, -16.5], ..., [-67.15, -17.98]] },
        "properties": { "id": "La Paz-Oruro", "origen": "La Paz",
                        "destino": "Oruro", "distancia": 230,
                        "trazado": "vial" } }
    ]},
    "routing": { "habilitado": true, "perfil": "driving",
                 "servicio_caido": false, "fallidos": [] }
  }
  ```
- **Qué hace:** el servicio recorre el grafo y arma los `Feature`. Solo incluye
  ciudades con coordenada válida; una carretera se dibuja únicamente si **sus dos
  extremos** están georreferenciados. Las coordenadas van en orden GeoJSON
  `[lon, lat]` (lo produce `Coordenada.to_geojson()` en el modelo).
- **Trazado vial (no línea recta):** si el enrutamiento está habilitado, cada
  carretera consulta su geometría real a **OSRM** (`RoutingService`) y la
  `LineString` sigue las carreteras (decenas de puntos), con
  `"trazado": "vial"`. Si OSRM no devuelve ruta o está caído, se usa el respaldo
  de **dos puntos en línea recta** con `"trazado": "recta"`. Las geometrías
  viales se **cachean en disco** (`*_rutas_viales.json`) para no reconsultar
  OSRM en cada carga.
- **Meta `routing`:** informa a la Vista el estado del enrutamiento —
  `habilitado` (config), `perfil` (p. ej. `driving`), `servicio_caido` (OSRM no
  respondió: respaldo recto global) y `fallidos` (carreteras concretas sin ruta
  vial). `map.js` usa esta meta para mostrar un aviso al usuario
  (`avisarTrazadoVial`).

---

### 3.3 API · Algoritmos

#### 5) `POST /api/todas-rutas` — DFS: todas las rutas
- **Backend:** `api_todas_rutas()` — `api_controller.py:L95-L119`
- **Frontend:** `calcularDFS()` — `app.js:L126-L145` (`postJSON` en `app.js:L130`).
  Se dispara con el botón *Todas las rutas (DFS)* (`index.html:L59`).
- **Envía (JSON):** `{ "origen": "La Paz", "destino": "Tarija" }`
- **Qué hace:** valida las ciudades y llama a `grafo.dfs_todas_rutas(...)`
  (backtracking). Ordena las rutas por número de paradas.
- **Respuesta:** `{ "origen", "destino", "total", "rutas": [ {camino, distancia,
  tiempo, peaje, paradas} ] }`

#### 6) `GET /api/matriz` — Matriz de adyacencia
- **Backend:** `api_matriz()` — `api_controller.py:L122-L132`
- **Frontend:** `mostrarMatriz()` — `app.js:L172-L189` (`fetch` en `app.js:L175`).
  Se dispara con el botón *Matriz* (`index.html:L11`) y con el `<select>` de
  criterio dentro del modal (`index.html:L285`).
- **Envía:** el criterio por **querystring** → `/api/matriz?criterio=tiempo`.
- **Respuesta:** `{ "criterio", "ciudades": [...], "matriz": [[...], ...] }`
  donde `matriz[i][j]` es el costo directo entre ciudad `i` y `j` (0 si no hay).

#### 7) `POST /api/comparar` — Comparar BFS vs. Dijkstra
- **Backend:** `api_comparar()` — `api_controller.py:L135-L181`
- **Frontend:** `compararAlgoritmos()` — `app.js:L148-L169`
  (`postJSON` en `app.js:L152`). Botón *Comparar algoritmos* (`index.html:L62`).
- **Envía (JSON):** `{ "origen": "La Paz", "destino": "Tarija" }`
- **Qué hace:** calcula 1 ruta con BFS + 3 rutas con Dijkstra (distancia, tiempo,
  peaje) y las devuelve juntas para que el frontend resalte el mejor de cada
  columna.
- **Respuesta:** `{ "origen", "destino", "resultados": [ {algoritmo, camino,
  paradas, distancia, tiempo, peaje, (optimiza)} ] }`

---

### 3.4 API · Gestión de ciudades

#### 8) `GET /api/ciudades` — Listar ciudades
- **Backend:** `gestionar_ciudades()` (rama `GET`) — `api_controller.py:L187-L232`
- **Frontend:** `listarCiudades()` — `app.js:L116-L123` (`fetch` en `app.js:L117`).
  Botón *Listar ciudades* (`index.html:L125`).
- **Respuesta:** `[ {"nombre", "tipo", "conexiones"} ]`

#### 9) `POST /api/ciudades` — Agregar ciudad
- **Backend:** `gestionar_ciudades()` (rama `POST`) — `api_controller.py:L187-L232`
- **Frontend:** `agregarCiudad()` — `app.js:L49-L57` (`postJSON` en `app.js:L52`).
  Datos del `<form id="formCiudad">` (`index.html:L145`), botón *Agregar*
  (`index.html:L164`).
- **Envía (JSON):** `{ "nombre": "Sucre", "tipo": "comercial",
  "lat": -19.03, "lon": -65.26 }` — `lat`/`lon` son **opcionales** (el modal trae
  los campos `#ciudadLat`/`#ciudadLon`, o el botón *Elegir ubicación en el mapa*
  los rellena con `fijarUbicacion()` · `map.js:L270-L285`).
- **Qué hace:** valida que no exista; si vienen `lat`/`lon`, los valida con
  `Coordenada(lat, lon)` (modelo) — coordenada inválida → **400**. Llama a
  `grafo.agregar_ciudad(nombre, tipo, coordenada)` y **persiste** con
  `servicio.guardar()`.
- **Respuesta:** `{ "mensaje", "total_ciudades" }`

#### 10) `POST /api/eliminar-ciudad` — Eliminar ciudad
- **Backend:** `eliminar_ciudad()` — `api_controller.py:L235-L257`
- **Frontend:** `eliminarCiudad()` — `app.js:L59-L67` (`postJSON` en `app.js:L62`).
  `<select id="selectEliminarCiudad">` (`index.html:L177`), botón *Eliminar*
  (`index.html:L185`).
- **Envía (JSON):** `{ "nombre": "Sucre" }`
- **Qué hace:** elimina la ciudad y todas sus carreteras; persiste.
- **Respuesta:** `{ "mensaje", "conexiones_eliminadas", "ciudades_restantes" }`

#### 11) `GET /api/ciudad/<nombre>` — Detalle de una ciudad
- **Backend:** `obtener_ciudad()` — `api_controller.py:L260-L281`
- **Frontend:** `mostrarInfoCiudad()` — `map.js:L236-L255` (`fetch` en
  `map.js:L237`). Se dispara al hacer **clic** sobre una ciudad del mapa
  (handler `map.on('click', 'ciudades-punto', ...)` en `map.js:L185-L188`). En
  `index.html` abre el modal; en `resultado.html`, un popup sobre el mapa.
- **Envía:** el nombre en la **URL** → `/api/ciudad/La%20Paz`.
- **Respuesta:** `{ "nombre", "tipo", "conexiones", "coordenada": {lat, lon},
  "rutas": [...] }` o, si no existe, **404** `{ "error": "Ciudad no encontrada" }`.

---

### 3.5 API · Gestión de rutas / carreteras

#### 12) `GET /api/rutas` — Listar carreteras
- **Backend:** `gestionar_rutas()` (rama `GET`) — `api_controller.py:L287-L348`
- **Frontend:** `listarRutas()` — `app.js:L103-L114` (`fetch` en `app.js:L104`).
  Botón *Listar carreteras* (`index.html:L133`).
- **Respuesta:** `{ "total_rutas", "rutas": [ {origen, destino, distancia,
  tiempo, peaje} ] }`

#### 13) `POST /api/rutas` — Agregar carretera
- **Backend:** `gestionar_rutas()` (rama `POST`) — `api_controller.py:L287-L348`
- **Frontend:** `agregarRuta()` — `app.js:L69-L80` (`postJSON` en `app.js:L75`).
  Datos del `<form id="formRuta">` (`index.html:L196`), botón *Agregar*
  (`index.html:L229`).
- **Envía (JSON):** `{ "origen", "destino", "distancia", "tiempo", "peaje" }`
- **Qué hace:** valida números > 0, que las ciudades existan y que la ruta no
  exista; llama a `grafo.agregar_arista(...)` y persiste.
- **Respuesta:** `{ "mensaje": "Ruta agregada correctamente" }`

#### 14) `POST /api/eliminar-carretera` — Eliminar carretera
- **Backend:** `eliminar_carretera()` — `api_controller.py:L351-L383`
- **Frontend:** `eliminarRuta()` — `app.js:L82-L91` (`postJSON` en `app.js:L86`).
  `<select id="selectEliminarOrigen">` (`index.html:L243`) y
  `selectEliminarDestino` (`index.html:L249`), botón *Eliminar* (`index.html:L258`).
- **Envía (JSON):** `{ "origen", "destino" }`
- **Respuesta:** `{ "mensaje", "carretera_eliminada": {distancia, tiempo, peaje} }`

---

### 3.6 API · Estadísticas y reinicio

#### 15) `GET /api/estadisticas` — Resumen del grafo
- **Backend:** `obtener_estadisticas()` — `api_controller.py:L389-L394`
  (delega en `MapaService.estadisticas()`).
- **Frontend:** se llama en el arranque de la página, dentro del
  `DOMContentLoaded` de `app.js:L216-L224` (`fetch` en `app.js:L218`). Rellena
  las tarjetas `total-ciudades`, `total-rutas`, etc. (`index.html:L99-L116`).
- **Respuesta:** `{ "total_ciudades", "total_rutas", "distancia_promedio",
  "tiempo_promedio", "peaje_promedio" }`

#### 16) `POST /api/reset` — Restaurar mapa de ejemplo
- **Backend:** `reset_grafo()` — `api_controller.py:L397-L411`
- **Frontend:** `restaurarEjemplo()` — `app.js:L93-L100` (`postJSON` en
  `app.js:L95`). Botón *Restaurar* del topbar (`index.html:L14`).
- **Qué hace:** vuelve al mapa de los 9 departamentos de Bolivia y persiste.
- **Respuesta:** `{ "mensaje", "ciudades", "rutas" }`

---

## 4. Patrones de comunicación (cómo está hecho)

**Frontend — un único helper para POST con JSON** (`app.js:L21-L27`):

```js
function postJSON(url, body) {
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    }).then(r => r.json());
}
```

Las lecturas (`GET`) usan `fetch(url).then(r => r.json())` directamente.
Tras una mutación correcta, el frontend muestra un *toast* (`app.js:L29-L40`) y
recarga la página con `location.reload()` para repintar el mapa.

**Backend — helpers compartidos en `api_controller.py`:**

| Helper | Línea | Para qué |
|--------|-------|----------|
| `_servicio()` | `api_controller.py:L14-L15` | acceso al `MapaService` vía `current_app` |
| `_error(mensaje, codigo=400)` | `api_controller.py:L18-L20` | respuesta JSON de error **uniforme** |

Toda la validación devuelve errores con `_error(...)`, por ejemplo:
`return _error("La ciudad ya existe")` → `({"error": "..."}, 400)`.

**Errores globales** (404/500) → JSON, registrados en
`app/__init__.py` (`_registrar_errores`, `__init__.py:L39-L46`).

---

## 5. Ciclo de vida de una petición típica (ejemplo: agregar ciudad)

```
1. Usuario llena el modal y pulsa "Agregar"      index.html:L164
2. agregarCiudad() arma el JSON y llama postJSON  app.js:L49-L57
3. POST /api/ciudades  ── { nombre, tipo } ─────▶ red
4. gestionar_ciudades() valida la entrada         api_controller.py:L187-L232
5.   └▶ grafo.agregar_ciudad(...)   (MODELO)       models/grafo.py:L44-L52
6.   └▶ servicio.guardar()          (SERVICIO)     services/mapa_service.py:L152-L158
7. Responde { mensaje, total_ciudades } ◀──────── jsonify
8. El frontend muestra un toast y recarga          app.js:L52-L56
```

---

## 6. Mapa rápido de archivos

| Capa | Archivo | Contenido |
|------|---------|-----------|
| Entrada | `run.py` | arranca la app (`py run.py`, puerto 5057) |
| Config | `config.py` | `SECRET_KEY`, ruta de `mapa.json`, clave/centro/zoom del mapa |
| Seguridad | `.env` (no versionado) / `.env.example` | `MAPTILER_API_KEY` y opciones del mapa |
| Fábrica | `app/__init__.py` | `create_app()`, registra Blueprints y errores |
| Controlador (HTML) | `app/controllers/main_controller.py` | `/` y `/ruta` |
| Controlador (API) | `app/controllers/api_controller.py` | todos los `/api/*` |
| Servicio | `app/services/mapa_service.py` | persistencia, ejemplo, estadísticas, GeoJSON |
| Modelo | `app/models/grafo.py` | `Grafo`: BFS, DFS, Dijkstra, matriz |
| Modelo | `app/models/geo.py` | `Coordenada`: validación de lat/lon (WGS84) |
| Vista (HTML) | `app/templates/{base,index,resultado}.html` | estructura + carga de MapLibre GL JS |
| Vista (JS) | `app/static/js/app.js` | UI de la página principal + llamadas API |
| Vista (JS) | `app/static/js/map.js` | mapa real (MapLibre): `/api/map-config`, `/api/geojson` |

---

> **Nota sobre estilo:** todo el código Python sigue **PEP 8** (verificado con
> `pycodestyle`, 0 advertencias), manteniendo nombres, comentarios y *docstrings*
> en español.
