"""
CONTROLADOR API (JSON)
======================
Expone el grafo y sus algoritmos al frontend mediante endpoints REST bajo el
prefijo `/api`. Toda la lógica de dominio vive en el modelo (Grafo) y la
persistencia en el servicio (MapaService); aquí solo se valida la entrada y se
arma la respuesta JSON.
"""

from flask import Blueprint, jsonify, request, current_app

from app.models.geo import Coordenada

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _servicio():
    return current_app.servicio_mapa


def _error(mensaje, codigo=400):
    """Construye una respuesta JSON de error uniforme."""
    return jsonify({"error": mensaje}), codigo


# ---------------------------------------------------------------------------
# Visualización del grafo
# ---------------------------------------------------------------------------
@api_bp.route("/data")
def api_data():
    """Nodos (con tipo) y aristas del grafo para la visualización."""
    grafo = _servicio().grafo
    nodes = [
        {"id": c, "label": c, "tipo": grafo.tipos_ciudad.get(c, "normal")}
        for c in grafo.obtener_ciudades()
    ]

    edges = []
    vistas = set()
    for ciudad1, conexiones in grafo.adyacencia.items():
        for ciudad2, distancia, tiempo, peaje in conexiones:
            clave = tuple(sorted([ciudad1, ciudad2]))
            if clave not in vistas:
                vistas.add(clave)
                edges.append(
                    {
                        "from": ciudad1,
                        "to": ciudad2,
                        "distancia": int(distancia),
                        "tiempo": int(tiempo),
                        "peaje": int(peaje),
                        "id": f"{ciudad1}-{ciudad2}",
                    }
                )
    return jsonify({"nodes": nodes, "edges": edges})


# ---------------------------------------------------------------------------
# Mapa real (MapTiler + MapLibre GL JS)
# ---------------------------------------------------------------------------
@api_bp.route("/map-config")
def api_map_config():
    """Configuracion del mapa para el cliente.

    La clave de MapTiler se lee de la configuracion (variable de entorno) y
    se entrega aqui, NUNCA escrita en las plantillas ni en los .js estaticos.
    Si no hay clave, el cliente usa un mapa base de OpenStreetMap (respaldo de
    desarrollo). La proteccion real de la clave es la restriccion por dominio
    configurada en el panel de MapTiler.
    """
    cfg = current_app.config
    api_key = cfg.get("MAPTILER_API_KEY", "")
    estilo = cfg.get("MAP_STYLE", "streets-v2")

    config = {
        "provider": "maptiler" if api_key else "osm",
        "hasKey": bool(api_key),
        "center": [
            cfg.get("MAP_CENTER_LON", -64.9),
            cfg.get("MAP_CENTER_LAT", -16.9),
        ],
        "zoom": cfg.get("MAP_ZOOM", 4.6),
    }
    if api_key:
        config["styleUrl"] = (
            f"https://api.maptiler.com/maps/{estilo}/style.json"
            f"?key={api_key}"
        )
    return jsonify(config)


@api_bp.route("/geojson")
def api_geojson():
    """Datos georreferenciados (ciudades y carreteras) en formato GeoJSON."""
    return jsonify(_servicio().geojson())


# ---------------------------------------------------------------------------
# Algoritmos: DFS, matriz, comparación
# ---------------------------------------------------------------------------
@api_bp.route("/todas-rutas", methods=["POST"])
def api_todas_rutas():
    """DFS: todas las rutas posibles entre dos ciudades."""
    grafo = _servicio().grafo
    try:
        data = request.json or {}
        origen = data.get("origen", "").strip()
        destino = data.get("destino", "").strip()

        if not origen or not destino:
            return _error("Se requiere origen y destino")
        if origen == destino:
            return _error("Origen y destino deben ser distintos")

        ciudades = grafo.obtener_ciudades()
        if origen not in ciudades or destino not in ciudades:
            return _error("Alguna ciudad no existe")

        rutas = grafo.dfs_todas_rutas(origen, destino)
        return jsonify(
            {
                "origen": origen,
                "destino": destino,
                "total": len(rutas),
                "rutas": rutas,
            }
        )
    except Exception as e:  # noqa: BLE001
        return _error(str(e), 500)


@api_bp.route("/matriz")
def api_matriz():
    """Matriz de adyacencia según el criterio (distancia, tiempo o peaje)."""
    grafo = _servicio().grafo
    criterio = request.args.get("criterio", "distancia")
    if criterio not in ("distancia", "tiempo", "peaje"):
        criterio = "distancia"
    ciudades, matriz = grafo.obtener_matriz_adyacencia(criterio)
    return jsonify(
        {"criterio": criterio, "ciudades": ciudades, "matriz": matriz}
    )


@api_bp.route("/comparar", methods=["POST"])
def api_comparar():
    """Compara BFS y Dijkstra (3 criterios) para un par de ciudades."""
    grafo = _servicio().grafo
    try:
        data = request.json or {}
        origen = data.get("origen", "").strip()
        destino = data.get("destino", "").strip()

        if not origen or not destino or origen == destino:
            return _error("Se requieren dos ciudades distintas")

        ciudades = grafo.obtener_ciudades()
        if origen not in ciudades or destino not in ciudades:
            return _error("Alguna ciudad no existe")

        resultados = []

        camino_bfs = grafo.bfs(origen, destino)
        if camino_bfs:
            total = grafo.detalle_camino(camino_bfs)["total"]
            resultados.append(
                {
                    "algoritmo": "BFS · menos paradas",
                    "camino": camino_bfs,
                    "paradas": max(len(camino_bfs) - 2, 0),
                    **total,
                }
            )

        etiquetas = {
            "distancia": "Dijkstra · menor distancia",
            "tiempo": "Dijkstra · menor tiempo",
            "peaje": "Dijkstra · menor peaje",
        }
        for crit in ("distancia", "tiempo", "peaje"):
            camino, _ = grafo.dijkstra(origen, destino, crit)
            if camino:
                total = grafo.detalle_camino(camino)["total"]
                resultados.append(
                    {
                        "algoritmo": etiquetas[crit],
                        "optimiza": crit,
                        "camino": camino,
                        "paradas": max(len(camino) - 2, 0),
                        **total,
                    }
                )

        return jsonify(
            {"origen": origen, "destino": destino, "resultados": resultados}
        )
    except Exception as e:  # noqa: BLE001
        return _error(str(e), 500)


# ---------------------------------------------------------------------------
# Gestión de ciudades
# ---------------------------------------------------------------------------
@api_bp.route("/ciudades", methods=["GET", "POST"])
def gestionar_ciudades():
    servicio = _servicio()
    grafo = servicio.grafo

    if request.method == "POST":
        try:
            data = request.json or {}
            nombre = data.get("nombre", "").strip()
            if not nombre:
                return _error("El nombre de la ciudad es requerido")
            if nombre in grafo.obtener_ciudades():
                return _error("La ciudad ya existe")

            # Coordenadas opcionales: se validan en el modelo (Coordenada).
            coordenada = None
            lat, lon = data.get("lat"), data.get("lon")
            if lat not in (None, "") and lon not in (None, ""):
                try:
                    coordenada = Coordenada(lat, lon)
                except ValueError as ve:
                    return _error(str(ve))

            grafo.agregar_ciudad(
                nombre, data.get("tipo", "normal"), coordenada
            )
            servicio.guardar()
            return jsonify(
                {
                    "mensaje": f"Ciudad {nombre} agregada correctamente",
                    "total_ciudades": len(grafo.obtener_ciudades()),
                }
            )
        except Exception as e:  # noqa: BLE001
            return _error(str(e), 500)

    # GET
    try:
        return jsonify(
            [
                {
                    "nombre": ciudad,
                    "tipo": grafo.tipos_ciudad.get(ciudad, "normal"),
                    "conexiones": len(grafo.adyacencia.get(ciudad, [])),
                }
                for ciudad in grafo.obtener_ciudades()
            ]
        )
    except Exception as e:  # noqa: BLE001
        return _error(str(e), 500)


@api_bp.route("/eliminar-ciudad", methods=["POST"])
def eliminar_ciudad():
    """Elimina una ciudad y todas sus carreteras."""
    servicio = _servicio()
    grafo = servicio.grafo
    try:
        data = request.json or {}
        ciudad = data.get("nombre", "").strip()
        if not ciudad:
            return _error("Se requiere el nombre de la ciudad")
        if ciudad not in grafo.obtener_ciudades():
            return _error(f"La ciudad {ciudad} no existe")

        conexiones_eliminadas = len(grafo.adyacencia.get(ciudad, []))
        grafo.eliminar_ciudad(ciudad)
        servicio.guardar()
        return jsonify(
            {
                "mensaje": f"Ciudad {ciudad} eliminada correctamente",
                "conexiones_eliminadas": conexiones_eliminadas,
                "ciudades_restantes": len(grafo.obtener_ciudades()),
            }
        )
    except Exception as e:  # noqa: BLE001
        return _error(f"Error al eliminar ciudad: {e}", 500)


@api_bp.route("/ciudad/<nombre>")
def obtener_ciudad(nombre):
    grafo = _servicio().grafo
    if nombre in grafo.adyacencia:
        conexiones = [
            {
                "destino": destino,
                "distancia": int(distancia),
                "tiempo": int(tiempo),
                "peaje": int(peaje),
            }
            for (destino, distancia, tiempo, peaje) in grafo.adyacencia[nombre]
        ]
        coord = grafo.obtener_coordenada(nombre)
        return jsonify(
            {
                "nombre": nombre,
                "tipo": grafo.tipos_ciudad.get(nombre, "normal"),
                "conexiones": len(grafo.adyacencia[nombre]),
                "coordenada": coord.to_dict() if coord else None,
                "rutas": conexiones,
            }
        )
    return _error("Ciudad no encontrada", 404)


# ---------------------------------------------------------------------------
# Gestión de rutas / carreteras
# ---------------------------------------------------------------------------
@api_bp.route("/rutas", methods=["GET", "POST"])
def gestionar_rutas():
    servicio = _servicio()
    grafo = servicio.grafo

    if request.method == "POST":
        try:
            data = request.json or {}
            origen = data.get("origen", "").strip()
            destino = data.get("destino", "").strip()

            if not origen or not destino:
                return _error("Se requiere origen y destino")
            if origen == destino:
                return _error("No se puede crear una ruta a la misma ciudad")
            if origen not in grafo.obtener_ciudades():
                return _error(f"La ciudad {origen} no existe")
            if destino not in grafo.obtener_ciudades():
                return _error(f"La ciudad {destino} no existe")

            try:
                distancia = int(data.get("distancia", 0))
                tiempo = int(data.get("tiempo", 0))
                peaje = int(data.get("peaje", 0))
            except (ValueError, TypeError):
                return _error("Los valores deben ser números válidos")

            if distancia <= 0 or tiempo <= 0 or peaje < 0:
                return _error(
                    "Distancia y tiempo deben ser > 0 y el peaje >= 0"
                )

            if grafo.obtener_info_arista(origen, destino):
                return _error("Esta ruta ya existe")

            grafo.agregar_arista(origen, destino, distancia, tiempo, peaje)
            servicio.guardar()
            return jsonify({"mensaje": "Ruta agregada correctamente"})
        except Exception as e:  # noqa: BLE001
            return _error(str(e), 500)

    # GET
    try:
        rutas = []
        vistas = set()
        for ciudad1, conexiones in grafo.adyacencia.items():
            for ciudad2, distancia, tiempo, peaje in conexiones:
                clave = tuple(sorted([ciudad1, ciudad2]))
                if clave not in vistas:
                    vistas.add(clave)
                    rutas.append(
                        {
                            "origen": ciudad1,
                            "destino": ciudad2,
                            "distancia": int(distancia),
                            "tiempo": int(tiempo),
                            "peaje": int(peaje),
                        }
                    )
        return jsonify(
            {
                "total_rutas": len(rutas),
                "rutas": sorted(rutas, key=lambda x: x["origen"]),
            }
        )
    except Exception as e:  # noqa: BLE001
        return _error(str(e), 500)


@api_bp.route("/eliminar-carretera", methods=["POST"])
def eliminar_carretera():
    """Elimina una carretera específica entre dos ciudades."""
    servicio = _servicio()
    grafo = servicio.grafo
    try:
        data = request.json or {}
        origen = data.get("origen", "").strip()
        destino = data.get("destino", "").strip()
        if not origen or not destino:
            return _error("Se requieren origen y destino")

        info = grafo.obtener_info_arista(origen, destino)
        if not info:
            return _error(f"No existe carretera entre {origen} y {destino}")

        grafo.eliminar_arista(origen, destino)
        servicio.guardar()
        return jsonify(
            {
                "mensaje": (
                    f"Carretera entre {origen} y {destino} "
                    "eliminada correctamente"
                ),
                "carretera_eliminada": {
                    "distancia": int(info["distancia"]),
                    "tiempo": int(info["tiempo"]),
                    "peaje": int(info["peaje"]),
                },
            }
        )
    except Exception as e:  # noqa: BLE001
        return _error(f"Error al eliminar carretera: {e}", 500)


# ---------------------------------------------------------------------------
# Estadísticas y reinicio
# ---------------------------------------------------------------------------
@api_bp.route("/estadisticas")
def obtener_estadisticas():
    try:
        return jsonify(_servicio().estadisticas())
    except Exception as e:  # noqa: BLE001
        return _error(f"Error al calcular estadísticas: {e}", 500)


@api_bp.route("/reset", methods=["POST"])
def reset_grafo():
    """Restaura el mapa de ejemplo (departamentos de Bolivia)."""
    servicio = _servicio()
    try:
        servicio.restaurar_ejemplo()
        grafo = servicio.grafo
        total_rutas = sum(len(c) for c in grafo.adyacencia.values()) // 2
        return jsonify(
            {
                "mensaje": "Mapa de ejemplo restaurado correctamente",
                "ciudades": len(grafo.obtener_ciudades()),
                "rutas": total_rutas,
            }
        )
    except Exception as e:  # noqa: BLE001
        return _error(f"Error al reiniciar: {e}", 500)
