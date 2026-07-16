import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 1. Cargar las credenciales de Neon desde el archivo .env
load_dotenv()
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError("¡Error! No se encontró la variable DATABASE_URL en tu archivo .env")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Conectar a la Base de Datos
print("Conectando con la base de datos de Neon...")
engine = create_engine(database_url)

# Ruta de tu archivo CSV único
CSV_PATH = "powerdata/data/data1.csv"

try:
    print(f"\n📖 Leyendo el archivo completo: {CSV_PATH}...")
    df_original = pd.read_csv(CSV_PATH)

    # =========================================================================
    # 📌 LIMPIEZA DE COLUMNAS (Normalizado total a minúsculas)
    # =========================================================================
    df_original.columns = df_original.columns.str.strip().str.lower()
    print("✅ Cabeceras del CSV normalizadas con éxito.")

    # Convertir formatos de fecha para evitar fallos en Postgres
    df_original['birthdate'] = pd.to_datetime(df_original['birthdate'], errors='coerce').dt.date


    # =========================================================================
    # 📌 PASO 1: EXTRAER E IMPORTAR ATLETAS ÚNICOS (ON CONFLICT DO NOTHING)
    # =========================================================================
    print("\n🏃‍♂️ Procesando atletas únicos...")
    df_atletas_unicos = df_original[['name', 'sex', 'birthdate']].drop_duplicates(subset=['name']).copy()
    df_atletas_unicos['birthdate'] = df_atletas_unicos['birthdate'].fillna(pd.NaT)
    
    query_atleta = text("""
        INSERT INTO atletas (nombre, sexo, fecha_nacimiento)
        VALUES (:nombre, :sexo, :fecha_nacimiento)
        ON CONFLICT (nombre) DO NOTHING;
    """)
    
    with engine.begin() as conn:
        for _, row in df_atletas_unicos.iterrows():
            conn.execute(query_atleta, {
                "nombre": row['name'],
                "sexo": row['sex'],
                "fecha_nacimiento": row['birthdate'] if not pd.isna(row['birthdate']) else None
            })
    print("✅ Proceso de atletas completado (sin duplicados).")


    # =========================================================================
    # 📌 PASO 2: REGISTRAR EL CAMPEONATO
    # =========================================================================
    print("\n🏆 Procesando campeonato...")
    df_campeonato = pd.DataFrame([{
        "nombre": "Copa Iron Fira",
        "anio": 2026,
        "fecha": "2026-05-15",
        "ciudad": "Barcelona"
    }])
    
    try:
        df_campeonato.to_sql("campeonatos", con=engine, if_exists="append", index=False)
        print("✅ Registrando campeonato nuevo en la base de datos...")
    except Exception:
        print("ℹ️ El campeonato ya estaba registrado, continuamos...")


    # =========================================================================
    # 📌 PASO 3: MAPEAR LOS IDs PARA LA TABLA 'RESULTADOS'
    # =========================================================================
    print("\n🔗 Vinculando IDs para estructurar los resultados relacionales...")
    db_atletas = pd.read_sql("SELECT id_atleta, nombre FROM atletas", con=engine)
    db_campeonatos = pd.read_sql("SELECT id_campeonato, nombre FROM campeonatos", con=engine)

    # Cruzamos usando 'name' en minúsculas del CSV con el 'nombre' de la BD
    df_con_atleta_id = pd.merge(
        df_original,
        db_atletas,
        left_on="name",
        right_on="nombre",
        how="inner"
    )

    id_campeonato_actual = db_campeonatos['id_campeonato'].max()
    df_con_atleta_id['id_campeonato'] = id_campeonato_actual


    # =========================================================================
    # 📌 PASO 4: IMPORTAR RESULTADOS CON TODAS LAS VARIABLES EN LA NUEVA TABLA
    # =========================================================================
    print("\n🏋️‍♂️ Mapeando absolutamente todas las variables de levantamiento...")
    
    df_resultados = pd.DataFrame()
    
    # IDs relacionales
    df_resultados['id_atleta'] = df_con_atleta_id['id_atleta']
    df_resultados['id_campeonato'] = df_con_atleta_id['id_campeonato']
    
    # Información General del Atleta
    df_resultados['place'] = df_con_atleta_id['place']
    df_resultados['age'] = df_con_atleta_id['age'].fillna(0)
    df_resultados['equipment'] = df_con_atleta_id['equipment']
    df_resultados['division'] = df_con_atleta_id['division']
    df_resultados['lot'] = df_con_atleta_id['lot'].fillna(0)
    df_resultados['bodyweight'] = df_con_atleta_id['bodyweightkg'].fillna(0)
    df_resultados['weight_class'] = df_con_atleta_id['weightclasskg']
    
    # Intentos y mejores marcas de Sentadilla (Squat)
    df_resultados['squat1'] = df_con_atleta_id['squat1kg'].fillna(0)
    df_resultados['squat2'] = df_con_atleta_id['squat2kg'].fillna(0)
    df_resultados['squat3'] = df_con_atleta_id['squat3kg'].fillna(0)
    # 🌟 Solucionado: Mapeamos desde 'best3squatkg' del CSV
    df_resultados['best_squat'] = df_con_atleta_id['best3squatkg'].fillna(0)
    
    # Intentos y mejores marcas de Press de Banca (Bench)
    df_resultados['bench1'] = df_con_atleta_id['bench1kg'].fillna(0)
    df_resultados['bench2'] = df_con_atleta_id['bench2kg'].fillna(0)
    df_resultados['bench3'] = df_con_atleta_id['bench3kg'].fillna(0)
    # 🌟 Solucionado: Mapeamos desde 'best3benchkg' del CSV
    df_resultados['best_bench'] = df_con_atleta_id['best3benchkg'].fillna(0)
    
    # Intentos y mejores marcas de Peso Muerto (Deadlift)
    df_resultados['deadlift1'] = df_con_atleta_id['deadlift1kg'].fillna(0)
    df_resultados['deadlift2'] = df_con_atleta_id['deadlift2kg'].fillna(0)
    df_resultados['deadlift3'] = df_con_atleta_id['deadlift3kg'].fillna(0)
    # 🌟 Solucionado: Mapeamos desde 'best3deadliftkg' del CSV
    df_resultados['best_deadlift'] = df_con_atleta_id['best3deadliftkg'].fillna(0)
    
    # Total de la competición
    df_resultados['total'] = df_con_atleta_id['totalkg'].fillna(0)

    print(f"Subiendo {len(df_resultados)} registros completos a la tabla 'resultados' de Neon...")
    
    # Insertamos los datos completos
    df_resultados.to_sql("resultados", con=engine, if_exists="append", index=False)

    print("\n🎉 ¡ÉXITO TOTAL! Tu tabla 'resultados' ha sido importada con el 100% de los datos y variables correctas. 🚀")

except Exception as e:
    print(f"\n❌ Ocurrió un error durante la importación: {e}")