import os
import math
import pandas as pd
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url)

app = Flask(__name__)

# 🧮 FUNCIÓN PARA CALCULAR PUNTOS GL
def calcular_puntos_gl(peso_corporal, total, sexo):
    if not peso_corporal or not total or peso_corporal <= 0 or total <= 0:
        return 0.0
    
    # Coeficientes oficiales de la fórmula GL
    if sexo.upper() == 'M':
        a, b, c = 1.1907, 1.3701, 0.0439
    else:  # 'F' o cualquier otra variante femenina
        a, b, c = 1.1090, 1.6372, 0.0448
        
    try:
        denominador = a - b * math.exp(-c * peso_corporal)
        puntos = total / (100 * denominador)
        return round(puntos, 2)
    except Exception:
        return 0.0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buscar', methods=['POST'])
def buscar():
    try:
        datos = request.get_json()
        total_usuario = float(datos.get('total', 0))
        peso_usuario = float(datos.get('bodyweight', 0))
        sexo_usuario = datos.get('sexo', 'M') # 'M' o 'F'
        categoria_filtro = datos.get('categoria', 'TODAS')

        # 1. Calcular puntos GL del usuario
        puntos_usuario = calcular_puntos_gl(peso_usuario, total_usuario, sexo_usuario)

        # 2. Construir la consulta SQL dinámica con filtros
        query_base = """
            SELECT a.nombre, a.sexo, r.bodyweight, r.weight_class, 
                   r.best_squat, r.best_bench, r.best_deadlift, r.total
            FROM resultados r
            JOIN atletas a ON r.id_atleta = a.id_atleta
            WHERE r.total >= :total
        """
        
        parametros = {"total": total_usuario}

        # Filtro de Sexo (si se especifica uno concreto)
        if sexo_usuario in ['M', 'F']:
            query_base += " AND a.sexo = :sexo"
            parametros["sexo"] = sexo_usuario

        # Filtro de Categoría de Peso (si no se elige "TODAS")
        if categoria_filtro != 'TODAS':
            query_base += " AND r.weight_class = :categoria"
            parametros["categoria"] = categoria_filtro

        query_base += " ORDER BY r.total ASC LIMIT 10"

        # 3. Consultar a Neon
        with engine.connect() as conn:
            result = conn.execute(text(query_base), parametros)
            columnas = result.keys()
            filas = [dict(zip(columnas, row)) for row in result]

        # 4. Calcular puntos GL para cada uno de los rivales encontrados
        atletas_lista = []
        for f in filas:
            gl_rival = calcular_puntos_gl(float(f['bodyweight']), float(f['total']), f['sexo'])
            atletas_lista.append({
                "nombre": f['nombre'],
                "sexo": f['sexo'],
                "bodyweight": float(f['bodyweight']),
                "weight_class": f['weight_class'],
                "sentadilla": float(f['best_squat']),
                "banca": float(f['best_bench']),
                "peso_muerto": float(f['best_deadlift']),
                "total": float(f['total']),
                "puntos_gl": gl_rival
            })

        return jsonify({
            "success": True,
            "puntos_usuario": puntos_usuario,
            "atletas": atletas_lista
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)