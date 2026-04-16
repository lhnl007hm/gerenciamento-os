# init_db.py - VERSÃO CORRIGIDA
import sqlite3
import os
import sys

# Tentar importar bcrypt
try:
    from flask_bcrypt import Bcrypt
except ImportError:
    print("⚠️  Instalando Flask-Bcrypt...")
    os.system(f"{sys.executable} -m pip install Flask-Bcrypt==1.0.1")
    from flask_bcrypt import Bcrypt

def criar_banco_dados():
    """Cria todas as tabelas do zero"""
    
    os.makedirs('instance', exist_ok=True)
    conn = sqlite3.connect('instance/sistema_os.db')
    cursor = conn.cursor()
    
    print("🔄 Criando banco de dados...")
    
    # Tabela Contratos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            ativo BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela Usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            email TEXT,
            nome_completo TEXT,
            contrato_id INTEGER NOT NULL,
            role TEXT DEFAULT 'user',
            ativo BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contrato_id) REFERENCES Contratos(id)
        )
    ''')
    
    # Tabela Atividades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Titulo TEXT NOT NULL,
            Data_Inicial TEXT NOT NULL,
            Data_Final TEXT,
            Descricao TEXT,
            Sistema TEXT NOT NULL,
            Status TEXT DEFAULT 'À Fazer',
            Tipo_de_Atividade TEXT NOT NULL,
            Numero_OS TEXT UNIQUE NOT NULL,
            contrato_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contrato_id) REFERENCES Contratos(id),
            FOREIGN KEY (usuario_id) REFERENCES Usuarios(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados criado!")

def criar_dados_iniciais():
    """Insere dados iniciais"""
    bcrypt = Bcrypt()
    conn = sqlite3.connect('instance/sistema_os.db')
    cursor = conn.cursor()
    
    # Criar contrato
    cursor.execute(
        "INSERT OR IGNORE INTO Contratos (nome, codigo) VALUES (?, ?)",
        ('Contrato Principal', 'CT001')
    )
    cursor.execute("SELECT id FROM Contratos WHERE codigo = 'CT001'")
    contrato_id = cursor.fetchone()[0]
    
    # Criar usuários
    usuarios = [
        ('admin', 'admin123', 'admin@exemplo.com', 'Administrador', 'admin'),
        ('gerente', 'gerente123', 'gerente@exemplo.com', 'Gerente', 'gerente'),
        ('tecnico', 'tecnico123', 'tecnico@exemplo.com', 'Técnico', 'user'),
    ]
    
    for username, senha, email, nome, role in usuarios:
        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
        cursor.execute('''
            INSERT OR IGNORE INTO Usuarios 
            (username, senha_hash, email, nome_completo, contrato_id, role)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, senha_hash, email, nome, contrato_id, role))
    
    conn.commit()
    conn.close()
    
    print("✅ Dados iniciais criados!")
    print("\n🔑 CREDENCIAIS:")
    print("   Admin: admin / admin123")
    print("   Gerente: gerente / gerente123")
    print("   Técnico: tecnico / tecnico123")

if __name__ == '__main__':
    print("🚀 INICIALIZANDO SISTEMA")
    criar_banco_dados()
    criar_dados_iniciais()
    print("\n✨ Execute: python app.py")