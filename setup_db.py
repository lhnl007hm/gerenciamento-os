# setup_db.py
import sqlite3
import os

os.makedirs('instance', exist_ok=True)
conn = sqlite3.connect('instance/sistema_os.db')
cursor = conn.cursor()

# Tabelas básicas
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Contratos (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        codigo TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS Usuarios (
        id INTEGER PRIMARY KEY,
        username TEXT,
        senha_hash TEXT,
        contrato_id INTEGER,
        role TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS Atividades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Titulo TEXT,
        Data_Inicial TEXT,
        Data_Final TEXT,
        Descricao TEXT,
        Sistema TEXT,
        Status TEXT,
        Tipo_de_Atividade TEXT,
        Numero_OS TEXT,
        contrato_id INTEGER,
        usuario_id INTEGER
    )
''')

# Dados iniciais
cursor.execute("INSERT OR IGNORE INTO Contratos VALUES (1, 'Principal', 'CT001')")
cursor.execute("INSERT OR IGNORE INTO Usuarios VALUES (1, 'admin', 'admin123', 1, 'admin')")

conn.commit()
conn.close()

print("✅ Banco criado!")