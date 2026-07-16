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
        sexo = datos.get('sexo', 'Cualquiera')
        categoria = datos.get('categoria', 'Cualquiera')
        nivel_camp = datos.get('nivel', 'Cualquiera')

        condiciones = []
        parametros = {"total": total_usuario}

        if sexo != 'Cualquiera':
            condiciones.append("a.sexo = :sexo")
            parametros["sexo"] = sexo

        if categoria != 'Cualquiera':
            cat_limpia = categoria.replace('-', '').replace('kg', '').strip()
            condiciones.append("REPLACE(REPLACE(r.weight_class, '-', ''), 'kg', '') = :categoria_limpia")
            parametros["categoria_limpia"] = cat_limpia

        if nivel_camp != 'Cualquiera':
            condiciones.append("c.nivel = :nivel")
            parametros["nivel"] = int(nivel_camp)

        str_condiciones = " AND " + " AND ".join(condiciones) if condiciones else ""

        query_rivales = f"""
            SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, 
                   r.best_squat, r.best_bench, r.best_deadlift, r.total,
                   c.nombre as meet_name, c.nivel
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
            WHERE r.total > :total {str_condiciones}
            ORDER BY r.total ASC 
            LIMIT 10
        """

        query_exactos = f"""
            SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, 
                   r.best_squat, r.best_bench, r.best_deadlift, r.total,
                   c.nombre as meet_name, c.nivel
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
            WHERE r.total = :total {str_condiciones}
            ORDER BY r.bodyweight ASC
        """

        # NUEVO: Obtenemos también las medias individuales de S, B y D
        query_estadisticas = f"""
            SELECT AVG(r.total) as media, STDDEV(r.total) as desviacion,
                   AVG(r.best_squat) as avg_squat,
                   AVG(r.best_bench) as avg_bench,
                   AVG(r.best_deadlift) as avg_deadlift
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            JOIN campeonatos c ON r.id_campeonato = c.id_campeonato
            WHERE 1=1 {str_condiciones}
        """

        with engine.connect() as conn:
            res_rivales = conn.execute(text(query_rivales), parametros)
            rivales_filas = [dict(zip(res_rivales.keys(), row)) for row in res_rivales]

            res_exactos = conn.execute(text(query_exactos), parametros)
            exactos_filas = [dict(zip(res_exactos.keys(), row)) for row in res_exactos]

            res_stats = conn.execute(text(query_estadisticas), parametros).fetchone()
            media = float(res_stats[0]) if res_stats and res_stats[0] is not None else 0.0
            desviacion = float(res_stats[1]) if res_stats and res_stats[1] is not None else 0.0
            avg_squat = float(res_stats[2]) if res_stats and res_stats[2] is not None else 0.0
            avg_bench = float(res_stats[3]) if res_stats and res_stats[3] is not None else 0.0
            avg_deadlift = float(res_stats[4]) if res_stats and res_stats[4] is not None else 0.0

        def mapear_resultados(filas):
            lista = []
            for f in filas:
                lista.append({
                    "nombre": f['nombre'],
                    "sexo": f['sexo'],
                    "bodyweight": float(f['bodyweight']),
                    "weight_class": f['weight_class'],
                    "sentadilla": float(f['best_squat']),
                    "banca": float(f['best_bench']),
                    "peso_muerto": float(f['best_deadlift']),
                    "total": float(f['total']),
                    "campeonato": f['meet_name'],
                    "nivel": f['nivel']
                })
            return lista

        return jsonify({
            "success": True,
            "rivales": mapear_resultados(rivales_filas),
            "empates": mapear_resultados(exactos_filas),
            "estadisticas": {
                "media": media,
                "desviacion": desviacion if desviacion > 0 else 50.0,
                "avg_squat": avg_squat,
                "avg_bench": avg_bench,
                "avg_deadlift": avg_deadlift
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)