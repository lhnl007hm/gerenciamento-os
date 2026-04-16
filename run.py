# run.py
from app import app

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Sistema de Gestão de OS")
    print("=" * 50)
    print("📍 Acesse: http://localhost:5000")
    print("🔑 Login: admin / admin123")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)