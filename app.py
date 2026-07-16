import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")

# Corrección para compatibilidad de PostgreSQL en Render/Heroku
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

        # --- CONSTRUCCIÓN DINÁMICA DE LA CONSULTA SQL ---
        condiciones = []
        parametros = {"total": total_usuario}

        # 1. Filtro de Sexo
        if sexo != 'Cualquiera':
            condiciones.append("a.sexo = :sexo")
            parametros["sexo"] = sexo

        # 2. Filtro de Categoría de Peso Inteligente (Limpia '-' y 'kg' de ambos lados)
        if categoria != 'Cualquiera':
            cat_limpia = categoria.replace('-', '').replace('kg', '').strip()
            condiciones.append("REPLACE(REPLACE(r.weight_class, '-', ''), 'kg', '') = :categoria_limpia")
            parametros["categoria_limpia"] = cat_limpia

        # 3. Filtro de Nivel de Campeonato
        if nivel_camp != 'Cualquiera':
            condiciones.append("c.nivel = :nivel")
            parametros["nivel"] = int(nivel_camp)

        # Unir condiciones si existen
        str_condiciones = " AND " + " AND ".join(condiciones) if condiciones else ""

        # CONSULTA 1: Los 10 rivales con total superior
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

        # CONSULTA 2: Todos los atletas que tienen exactamente tu mismo total
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

        with engine.connect() as conn:
            # Ejecutar consulta de rivales
            res_rivales = conn.execute(text(query_rivales), parametros)
            rivales_filas = [dict(zip(res_rivales.keys(), row)) for row in res_rivales]

            # Ejecutar consulta de empates exactos
            res_exactos = conn.execute(text(query_exactos), parametros)
            exactos_filas = [dict(zip(res_exactos.keys(), row)) for row in res_exactos]

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
            "empates": mapear_resultados(exactos_filas)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)