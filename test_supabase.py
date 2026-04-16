import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

database_url = os.environ.get('DATABASE_URL')
print(f"URL: {database_url}")

try:
    result = urlparse(database_url)
    
    # Forçar IPv4
    conn = psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        sslmode='require',
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30
    )
    print("✅ Conexão bem sucedida!")
    
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    print(f"📊 Usuários encontrados: {cur.fetchone()[0]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Erro: {e}")