import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url)

app = Flask(__name__)

@app.route('/')
def index():
    # Renderiza la página principal
    return render_template('index.html')

@app.route('/buscar', methods=['POST'])
def buscar():
    try:
        # Obtener el total que ingresó el usuario
        datos = request.get_json()
        total_usuario = float(datos.get('total', 0))
        
        # Consulta SQL para buscar los 10 atletas con un total igual o mayor
        # Ordenados de forma ascendente para mostrar los más cercanos a su total primero
        query = text("""
            SELECT a.nombre, r.total, r.bodyweight, r.best_squat, r.best_bench, r.best_deadlift
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            WHERE r.total >= :total_usuario
            ORDER BY r.total ASC
            LIMIT 10;
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"total_usuario": total_usuario})
            atletas = []
            for row in result:
                atletas.append({
                    "nombre": row.nombre,
                    "total": float(row.total),
                    "bodyweight": float(row.bodyweight),
                    "sentadilla": float(row.best_squat),
                    "banca": float(row.best_bench),
                    "peso_muerto": float(row.best_deadlift)
                })
                
        return jsonify({"success": True, "atletas": atletas})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    # Permite tomar el puerto dinámico que asigne internet
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)