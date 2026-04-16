# manage.py - Gerenciador de usuários e contratos
import sqlite3
import sys

def get_db():
    conn = sqlite3.connect('instance/database.db')
    conn.row_factory = sqlite3.Row
    return conn

def listar_contratos():
    conn = get_db()
    contratos = conn.execute("SELECT * FROM contratos").fetchall()
    print("\n=== CONTRATOS ===")
    for c in contratos:
        print(f"ID: {c['id']} | Código: {c['codigo']} | Nome: {c['nome']}")
    conn.close()

def criar_contrato(nome, codigo):
    conn = get_db()
    try:
        conn.execute("INSERT INTO contratos (nome, codigo) VALUES (?, ?)", (nome, codigo))
        conn.commit()
        print(f"✅ Contrato '{nome}' criado com sucesso!")
    except sqlite3.IntegrityError:
        print("❌ Erro: Código já existe!")
    conn.close()

def listar_usuarios():
    conn = get_db()
    usuarios = conn.execute("""
        SELECT u.*, c.nome as contrato_nome 
        FROM usuarios u 
        LEFT JOIN contratos c ON u.contrato_id = c.id
    """).fetchall()
    print("\n=== USUÁRIOS ===")
    for u in usuarios:
        print(f"ID: {u['id']} | Username: {u['username']} | Nome: {u['nome']} | Role: {u['role']} | Contrato: {u['contrato_nome']}")
    conn.close()

def criar_usuario(username, senha, nome, contrato_id, role='user'):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, senha, nome, contrato_id, role) VALUES (?, ?, ?, ?, ?)",
            (username, senha, nome, contrato_id, role)
        )
        conn.commit()
        print(f"✅ Usuário '{username}' criado com sucesso!")
    except sqlite3.IntegrityError:
        print("❌ Erro: Username já existe!")
    conn.close()

def resetar_senha(username, nova_senha):
    conn = get_db()
    conn.execute("UPDATE usuarios SET senha = ? WHERE username = ?", (nova_senha, username))
    conn.commit()
    print(f"✅ Senha do usuário '{username}' alterada!")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Comandos:")
        print("  python manage.py contratos listar")
        print("  python manage.py contratos criar <nome> <codigo>")
        print("  python manage.py usuarios listar")
        print("  python manage.py usuarios criar <username> <senha> <nome> <contrato_id> <role>")
        print("  python manage.py usuarios reset-senha <username> <nova_senha>")
        sys.exit(0)
    
    comando = sys.argv[1]
    
    if comando == 'contratos':
        acao = sys.argv[2]
        if acao == 'listar':
            listar_contratos()
        elif acao == 'criar':
            criar_contrato(sys.argv[3], sys.argv[4])
    
    elif comando == 'usuarios':
        acao = sys.argv[2]
        if acao == 'listar':
            listar_usuarios()
        elif acao == 'criar':
            criar_usuario(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7] if len(sys.argv) > 7 else 'user')
        elif acao == 'reset-senha':
            resetar_senha(sys.argv[3], sys.argv[4])