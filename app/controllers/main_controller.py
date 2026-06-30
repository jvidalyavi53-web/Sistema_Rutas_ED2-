"""
CONTROLADOR principal (vistas HTML)
===================================
Maneja la página principal y el cálculo de una ruta concreta, que se renderiza
con la plantilla `resultado.html`.
"""

from flask import Blueprint, render_template, request, current_app

main_bp = Blueprint("main", __name__)


def _servicio():
    return current_app.servicio_mapa


@main_bp.route("/")
def index():
    ciudades = _servicio().grafo.obtener_ciudades()
    return render_template("index.html", ciudades=ciudades)


@main_bp.route("/ruta", methods=["POST"])
def calcular_ruta():
    """Calcula una ruta con Dijkstra (por costo) o BFS (por paradas)."""
    grafo = _servicio().grafo
    origen = request.form.get("origen", "").strip()
    destino = request.form.get("destino", "").strip()
    criterio = request.form.get("criterio", "distancia")
    algoritmo = request.form.get("algoritmo", "dijkstra")

    base = dict(
        origen=origen,
        destino=destino,
        criterio=criterio,
        algoritmo=algoritmo,
        camino=[],
        costo_total=0,
        detalle=None,
        error=None,
    )

    try:
        if not origen or not destino:
            base["error"] = "Debe seleccionar origen y destino"
            return render_template("resultado.html", **base)

        if origen == destino:
            base["error"] = "El origen y destino no pueden ser iguales"
            return render_template("resultado.html", **base)

        if algoritmo == "bfs":
            camino = grafo.bfs(origen, destino)
            costo = len(camino) - 1 if camino else 0  # número de tramos
        else:
            algoritmo = "dijkstra"
            base["algoritmo"] = "dijkstra"
            camino, costo = grafo.dijkstra(origen, destino, criterio)
            costo = int(costo) if camino else 0

        if not camino:
            base["error"] = f"No existe ruta entre {origen} y {destino}"
            return render_template("resultado.html", **base)

        base.update(
            camino=camino,
            costo_total=costo,
            detalle=grafo.detalle_camino(camino),
        )
        return render_template("resultado.html", **base)
    except Exception as e:  # noqa: BLE001
        base["error"] = f"Error al calcular la ruta: {e}"
        return render_template("resultado.html", **base)
