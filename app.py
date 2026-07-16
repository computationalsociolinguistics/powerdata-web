import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buscar', methods=['POST'])
def buscar():
    try:
        datos = request.get_json()
        total_usuario = float(datos.get('total', 0))
        peso_usuario = float(datos.get('bodyweight', 0))

        # Consulta SQL limpia: Solo buscamos rivales con total igual o superior
        query = """
            SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, 
                   r.best_squat, r.best_bench, r.best_deadlift, r.total
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            WHERE r.total >= :total
            ORDER BY r.total ASC 
            LIMIT 10
        """
        
        parametros = {"total": total_usuario}

        with engine.connect() as conn:
            result = conn.execute(text(query), parametros)
            columnas = result.keys()
            filas = [dict(zip(columnas, row)) for row in result]

        atletas_lista = []
        for f in filas:
            atletas_lista.append({
                "nombre": f['nombre'],
                "sexo": f['sexo'],
                "bodyweight": float(f['bodyweight']),
                "weight_class": f['weight_class'],
                "sentadilla": float(f['best_squat']),
                "banca": float(f['best_bench']),
                "peso_muerto": float(f['best_deadlift']),
                "total": float(f['total'])
            })

        return jsonify({
            "success": True,
            "atletas": atletas_lista
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)