from sqlalchemy import create_engine, text

# URL da base no Render
DATABASE_URL = "postgresql://admin:ABH3mSHL6RMF6vcup5GnEBkN0PmzeDt6@dpg-d4773163jp1c73bqnubg-a.oregon-postgres.render.com/cupcakeapp"

# Cria engine global
engine = create_engine(DATABASE_URL)

def executar_query(sql, params=None):
    """Executa uma query SQL e retorna os resultados."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return result.fetchall()
    except Exception as e:
        print("❌ Erro ao executar query:", e)
        return None