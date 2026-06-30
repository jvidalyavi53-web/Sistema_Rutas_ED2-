"""
MODELO · Grafo
==============
Representa la red de ciudades (nodos) y carreteras (aristas) mediante una
**lista de adyacencia**. Cada arista guarda tres costos: distancia (km),
tiempo (min) y peaje (Bs). Incluye los algoritmos de recorrido y de caminos
mínimos que pide la consigna:

    * BFS .......... ruta con menos paradas (grafo no ponderado)
    * DFS .......... todas las rutas simples posibles (backtracking)
    * Dijkstra ..... ruta de menor costo según un criterio
    * Matriz de adyacencia

Esta clase es pura lógica de dominio: no sabe nada de Flask ni de disco.
"""

from collections import defaultdict, deque
import heapq

from app.models.geo import Coordenada


class Grafo:
    # Índice de cada costo en la tupla (vecino, distancia, tiempo, peaje)
    INDICES_COSTO = {"distancia": 1, "tiempo": 2, "peaje": 3}

    def __init__(self):
        self.adyacencia = defaultdict(list)
        self.tipos_ciudad = {}  # nombre -> tipo (capital, normal, ...)
        self.coordenadas = {}  # nombre -> Coordenada (ubicacion real)

    # ------------------------------------------------------------------ #
    # Construcción y mutación del grafo
    # ------------------------------------------------------------------ #
    def agregar_arista(self, ciudad1, ciudad2, distancia, tiempo=0, peaje=0):
        """Agrega una carretera bidireccional con sus tres costos."""
        self.adyacencia[ciudad1].append((ciudad2, distancia, tiempo, peaje))
        self.adyacencia[ciudad2].append((ciudad1, distancia, tiempo, peaje))

        if ciudad1 not in self.tipos_ciudad:
            self.tipos_ciudad[ciudad1] = "normal"
        if ciudad2 not in self.tipos_ciudad:
            self.tipos_ciudad[ciudad2] = "normal"

    def agregar_ciudad(self, nombre, tipo="normal", coordenada=None):
        """Agrega una ciudad (nodo), posiblemente aislada.

        `coordenada` es una instancia opcional de Coordenada para ubicar la
        ciudad sobre el mapa real. Si no se da, la ciudad existe en el grafo
        pero no se dibuja en el mapa geografico.
        """
        self.tipos_ciudad[nombre] = tipo
        if nombre not in self.adyacencia:
            self.adyacencia[nombre] = []
        if coordenada is not None:
            self.asignar_coordenada(nombre, coordenada)

    def eliminar_ciudad(self, ciudad):
        """Elimina una ciudad y todas sus carreteras."""
        if ciudad in self.adyacencia:
            for conexion in self.adyacencia[ciudad]:
                vecino = conexion[0]
                self.adyacencia[vecino] = [
                    c for c in self.adyacencia[vecino] if c[0] != ciudad
                ]
            del self.adyacencia[ciudad]
            self.tipos_ciudad.pop(ciudad, None)
            self.coordenadas.pop(ciudad, None)

    def eliminar_arista(self, ciudad1, ciudad2):
        """Elimina la carretera entre dos ciudades (en ambos sentidos)."""
        if ciudad1 in self.adyacencia:
            self.adyacencia[ciudad1] = [
                c for c in self.adyacencia[ciudad1] if c[0] != ciudad2
            ]
        if ciudad2 in self.adyacencia:
            self.adyacencia[ciudad2] = [
                c for c in self.adyacencia[ciudad2] if c[0] != ciudad1
            ]

    # ------------------------------------------------------------------ #
    # Consultas básicas
    # ------------------------------------------------------------------ #
    def obtener_ciudades(self):
        """Lista de todas las ciudades."""
        return list(self.adyacencia.keys())

    def obtener_ciudades_detalladas(self):
        """Lista de ciudades con su tipo y, si existe, su coordenada."""
        detalle = []
        for ciudad in self.obtener_ciudades():
            coord = self.coordenadas.get(ciudad)
            detalle.append(
                {
                    "nombre": ciudad,
                    "tipo": self.tipos_ciudad.get(ciudad, "normal"),
                    "coordenada": coord.to_dict() if coord else None,
                }
            )
        return detalle

    # ------------------------------------------------------------------ #
    # Coordenadas geograficas (relacion ciudad -> ubicacion real)
    # ------------------------------------------------------------------ #
    def asignar_coordenada(self, ciudad, coordenada):
        """Asocia una Coordenada validada a una ciudad existente.

        Lanza ValueError si la ciudad no existe o si `coordenada` no es una
        instancia de Coordenada (la validacion de rangos la hace Coordenada).
        """
        if ciudad not in self.adyacencia:
            raise ValueError(f"La ciudad {ciudad} no existe")
        if not isinstance(coordenada, Coordenada):
            raise ValueError("Se esperaba una instancia de Coordenada")
        self.coordenadas[ciudad] = coordenada

    def obtener_coordenada(self, ciudad):
        """Devuelve la Coordenada de una ciudad o None si no tiene."""
        return self.coordenadas.get(ciudad)

    def obtener_info_arista(self, ciudad1, ciudad2):
        """Devuelve los costos de la carretera directa entre dos ciudades."""
        for conexion in self.adyacencia.get(ciudad1, []):
            if conexion[0] == ciudad2:
                return {
                    "distancia": conexion[1],
                    "tiempo": conexion[2],
                    "peaje": conexion[3],
                }
        return None

    # ------------------------------------------------------------------ #
    # Algoritmo: Dijkstra (ruta de menor costo)
    # ------------------------------------------------------------------ #
    def dijkstra(self, inicio, destino, criterio="distancia"):
        """Ruta de menor costo entre dos ciudades según el criterio elegido.

        Devuelve (camino, costo_total). Si no hay ruta: ([], inf).
        """
        if inicio not in self.adyacencia or destino not in self.adyacencia:
            return [], float("inf")
        if inicio == destino:
            return [inicio], 0

        idx = self.INDICES_COSTO.get(criterio, 1)

        dist = {nodo: float("inf") for nodo in self.adyacencia}
        dist[inicio] = 0
        prev = {inicio: None}
        pq = [(0, inicio)]

        while pq:
            costo_actual, nodo_actual = heapq.heappop(pq)
            if costo_actual > dist[nodo_actual]:
                continue
            if nodo_actual == destino:
                break

            for conexion in self.adyacencia[nodo_actual]:
                vecino = conexion[0]
                try:
                    costo_arista = float(conexion[idx])
                except (ValueError, TypeError, IndexError):
                    costo_arista = float("inf")

                nuevo_costo = costo_actual + costo_arista
                if nuevo_costo < dist[vecino]:
                    dist[vecino] = nuevo_costo
                    prev[vecino] = nodo_actual
                    heapq.heappush(pq, (nuevo_costo, vecino))

        if dist[destino] == float("inf"):
            return [], float("inf")

        camino = []
        nodo = destino
        while nodo is not None:
            camino.insert(0, nodo)
            nodo = prev.get(nodo)
        return camino, dist[destino]

    # ------------------------------------------------------------------ #
    # Algoritmo: BFS (menos paradas, grafo no ponderado)
    # ------------------------------------------------------------------ #
    def bfs(self, inicio, destino):
        """Ruta con MENOR número de paradas, ignorando los pesos.

        Devuelve la lista de ciudades del camino (vacía si no hay ruta).
        """
        if inicio not in self.adyacencia or destino not in self.adyacencia:
            return []
        if inicio == destino:
            return [inicio]

        visitados = {inicio}
        cola = deque([[inicio]])  # cada elemento es un camino parcial

        while cola:
            camino = cola.popleft()
            nodo = camino[-1]
            for conexion in self.adyacencia[nodo]:
                vecino = conexion[0]
                if vecino == destino:
                    return camino + [vecino]
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append(camino + [vecino])
        return []

    # ------------------------------------------------------------------ #
    # Algoritmo: DFS (todas las rutas simples)
    # ------------------------------------------------------------------ #
    def dfs_todas_rutas(self, inicio, destino, max_rutas=300):
        """Enumera TODAS las rutas simples (sin repetir ciudades) entre
        origen y destino usando DFS con backtracking.

        Devuelve una lista de dicts con el camino, sus costos y paradas.
        `max_rutas` evita la explosión combinatoria en grafos muy conectados.
        """
        if inicio not in self.adyacencia or destino not in self.adyacencia:
            return []

        rutas = []
        visitados = set()

        def _dfs(nodo, camino):
            if len(rutas) >= max_rutas:
                return
            if nodo == destino:
                rutas.append(list(camino))
                return
            visitados.add(nodo)
            for conexion in self.adyacencia[nodo]:
                vecino = conexion[0]
                if vecino not in visitados:
                    camino.append(vecino)
                    _dfs(vecino, camino)
                    camino.pop()
            visitados.remove(nodo)

        _dfs(inicio, [inicio])

        resultado = []
        for camino in rutas:
            costos = self._costos_camino(camino)
            resultado.append(
                {
                    "camino": camino,
                    "distancia": costos["distancia"],
                    "tiempo": costos["tiempo"],
                    "peaje": costos["peaje"],
                    "paradas": max(len(camino) - 2, 0),
                }
            )
        resultado.sort(key=lambda r: (len(r["camino"]), r["distancia"]))
        return resultado

    # ------------------------------------------------------------------ #
    # Utilidades de costos / detalle
    # ------------------------------------------------------------------ #
    def _costos_camino(self, camino):
        """Suma los costos (distancia, tiempo, peaje) de un camino."""
        total = {"distancia": 0, "tiempo": 0, "peaje": 0}
        for i in range(len(camino) - 1):
            info = self.obtener_info_arista(camino[i], camino[i + 1])
            if info:
                total["distancia"] += int(info["distancia"])
                total["tiempo"] += int(info["tiempo"])
                total["peaje"] += int(info["peaje"])
        return total

    def detalle_camino(self, camino):
        """Desglosa un camino en tramos con el costo de cada uno y los
        totales acumulados de los tres criterios."""
        tramos = []
        for i in range(len(camino) - 1):
            info = self.obtener_info_arista(camino[i], camino[i + 1])
            if info:
                tramos.append(
                    {
                        "origen": camino[i],
                        "destino": camino[i + 1],
                        "distancia": int(info["distancia"]),
                        "tiempo": int(info["tiempo"]),
                        "peaje": int(info["peaje"]),
                    }
                )
        return {"tramos": tramos, "total": self._costos_camino(camino)}

    # ------------------------------------------------------------------ #
    # Representación: matriz de adyacencia
    # ------------------------------------------------------------------ #
    def obtener_matriz_adyacencia(self, criterio="distancia"):
        """Construye la matriz de adyacencia según el criterio elegido.

        matriz[i][j] = costo de la carretera directa entre ciudad i y j,
        o 0 si no existe conexión directa (también 0 en la diagonal).
        Devuelve (lista_ciudades_ordenadas, matriz).
        """
        idx = self.INDICES_COSTO.get(criterio, 1)

        ciudades = sorted(self.adyacencia.keys())
        pos = {c: i for i, c in enumerate(ciudades)}
        n = len(ciudades)
        matriz = [[0] * n for _ in range(n)]

        for ciudad, conexiones in self.adyacencia.items():
            for conexion in conexiones:
                i, j = pos[ciudad], pos[conexion[0]]
                matriz[i][j] = int(conexion[idx])

        return ciudades, matriz
