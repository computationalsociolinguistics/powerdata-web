import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
database_url = os.getenv("DATABASE_URL")

# Manejo de compatibilidad con Render/Heroku (asegurar el protocolo postgresql://)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Crear motor de conexión de base de datos
engine = create_engine(
    database_url, pool_size=10, max_overflow=20, pool_recycle=300
)

app = Flask(__name__)


@app.route("/")
def index():
    """Ruta principal que sirve la interfaz de usuario."""
    return render_template("index.html")


@app.route("/buscar", methods=["POST"])
def buscar():
    """
    Endpoint principal para procesar los levantamientos del usuario,
    calcular estadísticas de la categoría y encontrar competidores.
    """
    try:
        datos = request.get_json()

        # Datos del usuario
        total_usuario = float(datos.get("total", 0))
        bodyweight_usuario = float(datos.get("bodyweight", 0))

        # Filtros aplicados
        sexo = datos.get("sexo", "Cualquiera")
        categoria = datos.get("categoria", "Cualquiera")
        nivel = datos.get("nivel", "Cualquiera")

        # 1. CONSTRUCCIÓN DE FILTROS DINÁMICOS
        condiciones = []
        parametros = {
            "total_usuario": float(total_usuario),
            "sexo": sexo,
            "categoria": categoria,
        }

        # Filtro de sexo (en la tabla atletas 'a')
        if sexo != "Cualquiera":
            condiciones.append("a.sexo = :sexo")

        # Filtro de categoría (en la tabla resultados 'r')
        if categoria != "Cualquiera":
            condiciones.append("r.weight_class = :categoria")

        # Filtro de nivel (en la tabla campeonatos 'c')
        if nivel != "Cualquiera":
            condiciones.append("c.nivel = :nivel")
            parametros["nivel"] = int(nivel)

        # Unir condiciones
        where_clause = " AND ".join(condiciones) if condiciones else "1=1"

        # 2. CONSULTAS CON EL NUEVO JOIN A CAMPEONATOS
        with engine.connect() as conn:

            # --- Consulta A: Estadísticas con Join a Campeonatos ---
            query_stats = text(
                f"""
                SELECT 
                    COALESCE(AVG(r.total), 0) as media,
                    COALESCE(STDDEV(r.total), 0) as desviacion,
                    COALESCE(AVG(r.best_squat), 0) as avg_squat,
                    COALESCE(AVG(r.best_bench), 0) as avg_bench,
                    COALESCE(AVG(r.best_deadlift), 0) as avg_deadlift,
                    COALESCE(MAX(r.best_squat), 0) as max_squat,
                    COALESCE(MAX(r.best_bench), 0) as max_bench,
                    COALESCE(MAX(r.best_deadlift), 0) as max_deadlift
                FROM resultados r
                JOIN atletas a ON r.id_atleta = a.id_atleta
                JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
                WHERE {where_clause}
            """
            )

            res_stats = conn.execute(query_stats, parametros).mappings().first()

            # --- Consulta B: Atletas Empatados ---
            query_empates = text(
                f"""
                SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, c.nivel,
                       r.best_squat, r.best_bench, r.best_deadlift, r.total, c.nombre as campeonato
                FROM resultados r
                JOIN atletas a ON r.id_atleta = a.id_atleta
                JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
                WHERE {where_clause} AND r.total = :total_usuario
                ORDER BY r.bodyweight ASC
                LIMIT 10
            """
            )

            res_empates = conn.execute(query_empates, parametros).mappings().all()

            # --- Consulta C: Rivales Superiores ---
            query_rivales = text(
                f"""
                SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, c.nivel,
                       r.best_squat, r.best_bench, r.best_deadlift, r.total, c.nombre as campeonato
                FROM resultados r
                JOIN atletas a ON r.id_atleta = a.id_atleta
                JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
                WHERE {where_clause} AND r.total > :total_usuario
                ORDER BY r.total ASC, r.bodyweight ASC
                LIMIT 10
            """
            )

            res_rivales = conn.execute(query_rivales, parametros).mappings().all()

            # 3. PROCESAR Y FORMATEAR RESULTADOS PARA EL FRONTEND
            
            # Formatear estadísticas generales
            estadisticas = {
                "media": round(float(res_stats["media"]), 1),
                "desviacion": round(float(res_stats["desviacion"]), 1),
                "avg_squat": round(float(res_stats["avg_squat"]), 1),
                "avg_bench": round(float(res_stats["avg_bench"]), 1),
                "avg_deadlift": round(float(res_stats["avg_deadlift"]), 1),
                "max_squat": float(res_stats["max_squat"]),
                "max_bench": float(res_stats["max_bench"]),
                "max_deadlift": float(res_stats["max_deadlift"])
            }

            # Formatear lista de atletas empatados
            empates_lista = [
                {
                    "nombre": r["nombre"],
                    "sexo": r["sexo"],
                    "bodyweight": float(r["bodyweight"]),
                    "weight_class": r["weight_class"],
                    "nivel": int(r["nivel"]),
                    "sentadilla": float(r["best_squat"]),
                    "banca": float(r["best_bench"]),
                    "peso_muerto": float(r["best_deadlift"]),
                    "total": float(r["total"]),
                    "campeonato": r["campeonato"],
                }
                for r in res_empates
            ]

            # Formatear lista de rivales superiores
            rivales_lista = [
                {
                    "nombre": r["nombre"],
                    "sexo": r["sexo"],
                    "bodyweight": float(r["bodyweight"]),
                    "weight_class": r["weight_class"],
                    "nivel": int(r["nivel"]),
                    "sentadilla": float(r["best_squat"]),
                    "banca": float(r["best_bench"]),
                    "peso_muerto": float(r["best_deadlift"]),
                    "total": float(r["total"]),
                    "campeonato": r["campeonato"],
                }
                for r in res_rivales
            ]

        return jsonify(
            {
                "success": True,
                "estadisticas": estadisticas,
                "empates": empates_lista,
                "rivales": rivales_lista,
            }
        )

    except Exception as e:
        print(f"Error en el servidor: {e}")
        return jsonify(
            {
                "success": False,
                "error": "Ocurrió un error interno al procesar los datos.",
            }
        ), 500


if __name__ == "__main__":
    # Obtener el puerto asignado por Heroku/Render o usar el puerto 5000 en local
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)