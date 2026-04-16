import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

senhas_novas = {
    'admin': 'C0mp@$$$',
    'gerente': 'C0mp@$$$',
    'tecnico': 'C0mp@$$$'
}

for username, nova_senha in senhas_novas.items():
    cursor.execute("UPDATE usuarios SET senha = ? WHERE username = ?", (nova_senha, username))
    print(f"✅ Senha do usuário '{username}' alterada!")

conn.commit()
conn.close()
