"""
Application Factory
===================
Punto de ensamblaje de la aplicación Flask (patrón *application factory*).
Aquí se crea la app, se carga la configuración, se instancia el servicio del
mapa y se registran los Blueprints (controladores).

Arquitectura MVC del proyecto:

    app/models/        -> MODELO        (Grafo: datos + algoritmos)
    app/services/      -> SERVICIO      (persistencia y datos de ejemplo)
    app/controllers/   -> CONTROLADOR   (Blueprints con las rutas)
    app/templates/     -> VISTA (HTML)
    app/static/        -> VISTA (CSS/JS)
"""

from flask import Flask, jsonify

from config import Config
from app.services import MapaService, RoutingService


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Servicio del mapa compartido por toda la app (accesible vía current_app).
    # Se le inyecta el enrutamiento vial (OSRM) configurado por entorno; así
    # las carreteras se trazan siguiendo vías reales (no líneas rectas).
    app.servicio_mapa = MapaService(
        app.config["MAPA_FILE"],
        routing=RoutingService.desde_config(app.config),
    )

    # Registro de controladores (Blueprints)
    from app.controllers.main_controller import main_bp
    from app.controllers.api_controller import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    _registrar_errores(app)
    return app


def _registrar_errores(app):
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Error interno del servidor"}), 500
