# change_passwords.py
import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

senhas_novas = {
    'admin': 'Admin@2026#Seguro',
    'gerente': 'Gerente@2026#Seguro',
    'tecnico': 'Tecnico@2026#Seguro'
}

for username, nova_senha in senhas_novas.items():
    cursor.execute("UPDATE usuarios SET senha = ? WHERE username = ?", (nova_senha, username))
    print(f"✅ Senha do usuário '{username}' alterada!")

conn.commit()
conn.close()

print("\n🔐 NOVAS SENHAS:")
print("   admin   : Admin@2026#Seguro")
print("   gerente : Gerente@2026#Seguro")
print("   tecnico : Tecnico@2026#Seguro")
print("\n⚠️ ANOTE ESTAS SENHAS! GUARDE EM LOCAL SEGURO!")