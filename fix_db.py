# fix_db.py - Execute uma vez para corrigir a estrutura do banco
import sqlite3
import os

os.makedirs('instance', exist_ok=True)
conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

# Verificar e adicionar colunas faltantes na tabela usuarios
cursor.execute("PRAGMA table_info(usuarios)")
colunas_usuarios = [col[1] for col in cursor.fetchall()]

if 'email' not in colunas_usuarios:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    print("✅ Coluna 'email' adicionada à tabela usuarios")

if 'ativo' not in colunas_usuarios:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN ativo INTEGER DEFAULT 1")
    print("✅ Coluna 'ativo' adicionada à tabela usuarios")

# Verificar e adicionar colunas faltantes na tabela contratos
cursor.execute("PRAGMA table_info(contratos)")
colunas_contratos = [col[1] for col in cursor.fetchall()]

if 'ativo' not in colunas_contratos:
    cursor.execute("ALTER TABLE contratos ADD COLUMN ativo INTEGER DEFAULT 1")
    print("✅ Coluna 'ativo' adicionada à tabela contratos")

conn.commit()
conn.close()

print("\n🎉 Banco de dados atualizado com sucesso!")