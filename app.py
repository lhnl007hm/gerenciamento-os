# app.py - SISTEMA COMPASS OS (COMPATÍVEL SQLite + PostgreSQL)
import os
import sqlite3
import csv
import io
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from dotenv import load_dotenv

# Tentar importar psycopg2 (para PostgreSQL)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️ psycopg2 não instalado. Usando apenas SQLite.")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave-desenvolvimento-2026')


# Configurações
PREFIXOS_OS = {
    'Manutenção Preventiva': 'MP',
    'Manutenção Corretiva': 'MC',
    'Acompanhamento': 'AC',
    'Outros': 'OT'
}

CODIGOS_SISTEMA = {
    'SDAI': 'SDAI',
    'BMS': 'BMS',
    'SCA': 'SCA',
    'SAI': 'SAI',
    'Telecom': 'TEL'
}

# ============ BANCO DE DADOS ============
def get_db_connection():
    """Retorna conexão com o banco de dados"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        # PostgreSQL (Railway)
        result = urlparse(database_url)
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        return conn, 'postgres'
    else:
        # SQLite (desenvolvimento local)
        if not os.path.exists('instance'):
            os.makedirs('instance')
        conn = sqlite3.connect('instance/database.db')
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'

def execute_query(query, args=(), fetch_one=False, fetch_all=False, commit=False):
    """Executa query compatível com SQLite e PostgreSQL"""
    conn, db_type = get_db_connection()
    
    if db_type == 'postgres':
        # Converte ? para %s (PostgreSQL)
        query = query.replace('?', '%s')
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, args)
        
        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        
        if commit or not (fetch_one or fetch_all):
            conn.commit()
        
        cur.close()
    else:
        # SQLite
        cur = conn.cursor()
        cur.execute(query, args)
        
        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        
        if commit or not (fetch_one or fetch_all):
            conn.commit()
    
    conn.close()
    return result

def get_db():
    """Retorna conexão SQLite (para compatibilidade com código existente)"""
    conn, _ = get_db_connection()
    return conn

def init_db():
    """Cria tabelas se não existirem"""
    conn, db_type = get_db_connection()
    
    if db_type == 'postgres':
        cur = conn.cursor()
        
        # Tabela contratos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS contratos (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                codigo TEXT UNIQUE NOT NULL,
                ativo INTEGER DEFAULT 1
            )
        ''')
        
        # Tabela usuarios
        cur.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                nome TEXT,
                email TEXT,
                contrato_id INTEGER REFERENCES contratos(id),
                role TEXT DEFAULT 'user',
                ativo INTEGER DEFAULT 1
            )
        ''')
        
        # Tabela atividades
        cur.execute('''
            CREATE TABLE IF NOT EXISTS atividades (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                data_inicial TEXT NOT NULL,
                data_final TEXT,
                descricao TEXT,
                sistema TEXT NOT NULL,
                status TEXT DEFAULT 'À Fazer',
                tipo TEXT NOT NULL,
                numero_os TEXT UNIQUE NOT NULL,
                contrato_id INTEGER REFERENCES contratos(id),
                usuario_id INTEGER REFERENCES usuarios(id),
                created_at TEXT
            )
        ''')
        
        # Verificar se já existem dados
        cur.execute("SELECT COUNT(*) FROM contratos")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO contratos (nome, codigo) VALUES (%s, %s)", ('E-Business Park', 'EBP001'))
            cur.execute("INSERT INTO contratos (nome, codigo) VALUES (%s, %s)", ('Contrato Beta', 'CT002'))
            
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES (%s, %s, %s, %s, %s, %s)",
                       ('admin', 'Admin@2024#Seguro', 'Administrador', 'admin@compass.com.br', 1, 'admin'))
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES (%s, %s, %s, %s, %s, %s)",
                       ('gerente', 'Gerente@2024#Seguro', 'Gerente', 'gerente@compass.com.br', 1, 'gerente'))
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES (%s, %s, %s, %s, %s, %s)",
                       ('tecnico', 'Tecnico@2024#Seguro', 'Técnico', 'tecnico@compass.com.br', 1, 'tecnico'))
        
        conn.commit()
        cur.close()
    else:
        # SQLite
        cur = conn.cursor()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS contratos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                codigo TEXT UNIQUE NOT NULL,
                ativo INTEGER DEFAULT 1
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                nome TEXT,
                email TEXT,
                contrato_id INTEGER,
                role TEXT DEFAULT 'user',
                ativo INTEGER DEFAULT 1,
                FOREIGN KEY (contrato_id) REFERENCES contratos(id)
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS atividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                data_inicial TEXT NOT NULL,
                data_final TEXT,
                descricao TEXT,
                sistema TEXT NOT NULL,
                status TEXT DEFAULT 'À Fazer',
                tipo TEXT NOT NULL,
                numero_os TEXT UNIQUE NOT NULL,
                contrato_id INTEGER,
                usuario_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (contrato_id) REFERENCES contratos(id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        
        cur.execute("SELECT COUNT(*) FROM contratos")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO contratos (nome, codigo) VALUES ('E-Business Park', 'EBP001')")
            cur.execute("INSERT INTO contratos (nome, codigo) VALUES ('Contrato Beta', 'CT002')")
            
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('admin', 'Admin@2024#Seguro', 'Administrador', 'admin@compass.com.br', 1, 'admin')")
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('gerente', 'Gerente@2024#Seguro', 'Gerente', 'gerente@compass.com.br', 1, 'gerente')")
            cur.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('tecnico', 'Tecnico@2024#Seguro', 'Técnico', 'tecnico@compass.com.br', 1, 'tecnico')")
        
        conn.commit()
    
    conn.close()
    print("✅ Banco de dados inicializado!")
    # Inicializa banco quando o app sobe (Railway / Gunicorn)
with app.app_context():
    init_db()

# ============ DECORATORS ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar!', 'warning')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar!', 'warning')
            return redirect('/login')
        if session.get('role') != 'admin':
            flash('Acesso restrito a administradores!', 'danger')
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated_function

def admin_or_tecnico_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para acessar!', 'warning')
            return redirect('/login')
        if session.get('role') not in ['admin', 'tecnico']:
            flash('Acesso negado!', 'danger')
            return redirect('/metricas')
        return f(*args, **kwargs)
    return decorated_function

# ============ FUNÇÃO GERADORA DE OS ============
def gerar_numero_os(tipo_atividade, sistema, contrato_id):
    prefixo = PREFIXOS_OS.get(tipo_atividade, 'OT')
    cod_sistema = CODIGOS_SISTEMA.get(sistema, 'XXX')
    
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        result = execute_query(
            "SELECT COUNT(*) as total FROM atividades WHERE tipo = %s AND sistema = %s AND contrato_id = %s",
            (tipo_atividade, sistema, contrato_id),
            fetch_one=True
        )
        count = result['total'] + 1 if result else 1
    else:
        conn = get_db()
        cursor = conn.execute(
            "SELECT COUNT(*) as total FROM atividades WHERE tipo = ? AND sistema = ? AND contrato_id = ?",
            (tipo_atividade, sistema, contrato_id)
        )
        count = cursor.fetchone()['total'] + 1
        conn.close()
    
    return f"{prefixo}{cod_sistema}{count:03d}"

# ============ ROTAS PÚBLICAS ============
@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        senha = request.form['senha'].strip()
        
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and PSYCOPG2_AVAILABLE:
            user = execute_query(
                "SELECT u.*, c.nome as contrato_nome FROM usuarios u JOIN contratos c ON u.contrato_id = c.id WHERE u.username = %s AND u.senha = %s",
                (username, senha),
                fetch_one=True
            )
        else:
            conn = get_db()
            user = conn.execute(
                "SELECT u.*, c.nome as contrato_nome FROM usuarios u JOIN contratos c ON u.contrato_id = c.id WHERE u.username = ? AND u.senha = ?",
                (username, senha)
            ).fetchone()
            conn.close()
            user = dict(user) if user else None
        
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nome'] = user['nome']
            session['email'] = user['email'] if user.get('email') else 'master@compass.com.br'
            session['contrato_id'] = user['contrato_id']
            session['contrato_nome'] = user['contrato_nome']
            session['role'] = user['role']
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            
            if user['role'] == 'admin':
                return redirect('/admin/dashboard')
            elif user['role'] == 'gerente':
                return redirect('/metricas')
            else:
                return redirect('/dashboard')
        
        flash('Usuário ou senha inválidos!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ============ DASHBOARD (TÉCNICO) ============
@app.route('/dashboard')
@login_required
def dashboard():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        total = execute_query("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s", (session['contrato_id'],), fetch_one=True)['total']
        concluidas = execute_query("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'Concluído'", (session['contrato_id'],), fetch_one=True)['total']
        andamento = execute_query("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'Em Andamento'", (session['contrato_id'],), fetch_one=True)['total']
        afazer = execute_query("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'À Fazer'", (session['contrato_id'],), fetch_one=True)['total']
        recentes = execute_query("SELECT * FROM atividades WHERE contrato_id = %s ORDER BY id DESC LIMIT 5", (session['contrato_id'],), fetch_all=True)
    else:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ?", (session['contrato_id'],)).fetchone()['total']
        concluidas = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Concluído'", (session['contrato_id'],)).fetchone()['total']
        andamento = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Em Andamento'", (session['contrato_id'],)).fetchone()['total']
        afazer = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'À Fazer'", (session['contrato_id'],)).fetchone()['total']
        recentes = conn.execute("SELECT * FROM atividades WHERE contrato_id = ? ORDER BY id DESC LIMIT 5", (session['contrato_id'],)).fetchall()
        conn.close()
        recentes = [dict(r) for r in recentes] if recentes else []
    
    return render_template('dashboard.html', total=total, concluidas=concluidas, andamento=andamento, afazer=afazer, recentes=recentes)

@app.route('/atividades')
@login_required
@admin_or_tecnico_required
def atividades():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        atividades = execute_query("""
            SELECT a.*, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.contrato_id = %s
            ORDER BY a.id DESC
        """, (session['contrato_id'],), fetch_all=True)
        atividades = [dict(a) for a in atividades] if atividades else []
    else:
        conn = get_db()
        cursor = conn.execute("""
            SELECT a.*, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.contrato_id = ? 
            ORDER BY a.id DESC
        """, (session['contrato_id'],))
        atividades = [dict(row) for row in cursor.fetchall()]
        conn.close()
    
    return render_template('atividades.html', atividades=atividades)

@app.route('/atividades/nova', methods=['GET', 'POST'])
@login_required
@admin_or_tecnico_required
def nova_atividade():
    if request.method == 'POST':
        titulo = request.form['titulo']
        data_inicial = request.form['data_inicial']
        data_final = request.form.get('data_final', '')
        descricao = request.form.get('descricao', '')
        sistema = request.form['sistema']
        status = request.form['status']
        tipo = request.form['tipo']
        
        numero_os = gerar_numero_os(tipo, sistema, session['contrato_id'])
        
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and PSYCOPG2_AVAILABLE:
            execute_query('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, session['contrato_id'], session['user_id'], datetime.now().isoformat()), commit=True)
        else:
            conn = get_db()
            conn.execute('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, session['contrato_id'], session['user_id'], datetime.now().isoformat()))
            conn.commit()
            conn.close()
        
        flash(f'Atividade criada! OS: {numero_os}', 'success')
        return redirect('/atividades')
    
    return render_template('form.html', atividade=None)

@app.route('/atividades/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_or_tecnico_required
def editar_atividade(id):
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        atividade = execute_query("SELECT * FROM atividades WHERE id = %s AND contrato_id = %s", (id, session['contrato_id']), fetch_one=True)
    else:
        conn = get_db()
        atividade = conn.execute("SELECT * FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id'])).fetchone()
        conn.close()
        atividade = dict(atividade) if atividade else None
    
    if not atividade:
        flash('Atividade não encontrada!', 'danger')
        return redirect('/atividades')
    
    if request.method == 'POST':
        if database_url and PSYCOPG2_AVAILABLE:
            execute_query('''
                UPDATE atividades 
                SET titulo = %s, data_inicial = %s, data_final = %s, descricao = %s, sistema = %s, status = %s, tipo = %s
                WHERE id = %s
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], id), commit=True)
        else:
            conn = get_db()
            conn.execute('''
                UPDATE atividades 
                SET titulo = ?, data_inicial = ?, data_final = ?, descricao = ?, sistema = ?, status = ?, tipo = ?
                WHERE id = ?
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], id))
            conn.commit()
            conn.close()
        
        flash('Atividade atualizada!', 'success')
        return redirect('/atividades')
    
    return render_template('form.html', atividade=atividade)

@app.route('/atividades/<int:id>/excluir', methods=['POST'])
@login_required
@admin_or_tecnico_required
def excluir_atividade(id):
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        execute_query("DELETE FROM atividades WHERE id = %s AND contrato_id = %s", (id, session['contrato_id']), commit=True)
    else:
        conn = get_db()
        conn.execute("DELETE FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id']))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

# ============ MÉTRICAS ============
@app.route('/metricas')
@login_required
def metricas():
    database_url = os.environ.get('DATABASE_URL')
    mes_filtro = request.args.get('mes', '')
    
    if database_url and PSYCOPG2_AVAILABLE:
        where_clause = "WHERE contrato_id = %s"
        params = [session['contrato_id']]
        
        if mes_filtro:
            where_clause += " AND TO_CHAR(data_inicial::DATE, 'YYYY-MM') = %s"
            params.append(mes_filtro)
        
        por_tipo = execute_query(f'''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::DATE - data_inicial::DATE))/86400 ELSE NULL END)::numeric, 1) as media_dias
            FROM atividades 
            {where_clause}
            GROUP BY tipo
        ''', params, fetch_all=True)
        
        por_sistema = execute_query(f'''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades 
            {where_clause}
            GROUP BY sistema
        ''', params, fetch_all=True)
        
        stats = execute_query(f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::DATE - data_inicial::DATE))/86400 ELSE NULL END)::numeric, 1) as media_geral_dias
            FROM atividades
            {where_clause}
        ''', params, fetch_one=True)
        
        meses = execute_query('''
            SELECT DISTINCT TO_CHAR(data_inicial::DATE, 'YYYY-MM') as mes
            FROM atividades
            WHERE contrato_id = %s
            ORDER BY mes DESC
        ''', (session['contrato_id'],), fetch_all=True)
    else:
        conn = get_db()
        
        where_clause = "WHERE contrato_id = ?"
        params = [session['contrato_id']]
        
        if mes_filtro:
            where_clause += " AND strftime('%Y-%m', data_inicial) = ?"
            params.append(mes_filtro)
        
        por_tipo = conn.execute(f'''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_dias
            FROM atividades 
            {where_clause}
            GROUP BY tipo
        ''', params).fetchall()
        
        por_sistema = conn.execute(f'''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades 
            {where_clause}
            GROUP BY sistema
        ''', params).fetchall()
        
        stats = conn.execute(f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_geral_dias
            FROM atividades
            {where_clause}
        ''', params).fetchone()
        
        meses = conn.execute('''
            SELECT DISTINCT strftime('%Y-%m', data_inicial) as mes
            FROM atividades
            WHERE contrato_id = ?
            ORDER BY mes DESC
        ''', (session['contrato_id'],)).fetchall()
        
        conn.close()
        
        por_tipo = [dict(r) for r in por_tipo] if por_tipo else []
        por_sistema = [dict(r) for r in por_sistema] if por_sistema else []
        meses = [dict(r) for r in meses] if meses else []
        stats = dict(stats) if stats else {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    
    if stats is None:
        stats = {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    
    return render_template('metricas.html', por_tipo=por_tipo, por_sistema=por_sistema, stats=stats, meses=meses, mes_selecionado=mes_filtro)

@app.route('/metricas/exportar')
@login_required
def exportar_relatorio():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        atividades = execute_query('''
            SELECT numero_os, titulo, data_inicial, data_final, sistema, status, tipo, descricao
            FROM atividades WHERE contrato_id = %s ORDER BY data_inicial DESC
        ''', (session['contrato_id'],), fetch_all=True)
    else:
        conn = get_db()
        atividades = conn.execute('''
            SELECT numero_os, titulo, data_inicial, data_final, sistema, status, tipo, descricao
            FROM atividades WHERE contrato_id = ? ORDER BY data_inicial DESC
        ''', (session['contrato_id'],)).fetchall()
        conn.close()
        atividades = [dict(a) for a in atividades] if atividades else []
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['RELATÓRIO - ' + session['contrato_nome']])
    writer.writerow(['Gerado em: ' + datetime.now().strftime('%d/%m/%Y %H:%M')])
    writer.writerow([])
    writer.writerow(['Número OS', 'Título', 'Data Inicial', 'Data Final', 'Sistema', 'Status', 'Tipo'])
    
    for a in atividades:
        writer.writerow([a['numero_os'], a['titulo'], a['data_inicial'], a['data_final'] or '-', a['sistema'], a['status'], a['tipo']])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'relatorio_{datetime.now().strftime("%Y%m%d")}.csv')

# ============ ADMIN ============
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        total = execute_query("SELECT COUNT(*) as total FROM atividades", fetch_one=True)['total']
        concluidas = execute_query("SELECT COUNT(*) as total FROM atividades WHERE status = 'Concluído'", fetch_one=True)['total']
        andamento = execute_query("SELECT COUNT(*) as total FROM atividades WHERE status = 'Em Andamento'", fetch_one=True)['total']
        afazer = execute_query("SELECT COUNT(*) as total FROM atividades WHERE status = 'À Fazer'", fetch_one=True)['total']
        
        por_contrato = execute_query("""
            SELECT c.nome, COUNT(a.id) as total
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
            GROUP BY c.id
            ORDER BY total DESC
        """, fetch_all=True)
        
        recentes = execute_query("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC LIMIT 10
        """, fetch_all=True)
    else:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) as total FROM atividades").fetchone()['total']
        concluidas = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Concluído'").fetchone()['total']
        andamento = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Em Andamento'").fetchone()['total']
        afazer = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'À Fazer'").fetchone()['total']
        
        por_contrato = conn.execute("""
            SELECT c.nome, COUNT(a.id) as total
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
            GROUP BY c.id
            ORDER BY total DESC
        """).fetchall()
        
        recentes = conn.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC LIMIT 10
        """).fetchall()
        conn.close()
        
        por_contrato = [dict(r) for r in por_contrato] if por_contrato else []
        recentes = [dict(r) for r in recentes] if recentes else []
    
    return render_template('admin_dashboard.html', total=total, concluidas=concluidas, andamento=andamento, afazer=afazer, por_contrato=por_contrato, recentes=recentes)

@app.route('/admin/atividades')
@login_required
@admin_required
def admin_atividades():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        atividades = execute_query("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN contratos c ON a.contrato_id = c.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC
        """, fetch_all=True)
        atividades = [dict(a) for a in atividades] if atividades else []
    else:
        conn = get_db()
        cursor = conn.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN contratos c ON a.contrato_id = c.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC
        """)
        atividades = [dict(row) for row in cursor.fetchall()]
        conn.close()
    
    return render_template('admin_atividades.html', atividades=atividades)

@app.route('/admin/atividades/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_nova_atividade():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        contratos = execute_query("SELECT * FROM contratos WHERE ativo = 1", fetch_all=True)
    else:
        conn = get_db()
        contratos = conn.execute("SELECT * FROM contratos WHERE ativo = 1").fetchall()
        conn.close()
        contratos = [dict(c) for c in contratos] if contratos else []
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        data_inicial = request.form['data_inicial']
        data_final = request.form.get('data_final', '')
        descricao = request.form.get('descricao', '')
        sistema = request.form['sistema']
        status = request.form['status']
        tipo = request.form['tipo']
        contrato_id = request.form['contrato_id']
        
        numero_os = gerar_numero_os(tipo, sistema, contrato_id)
        
        if database_url and PSYCOPG2_AVAILABLE:
            execute_query('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, contrato_id, session['user_id'], datetime.now().isoformat()), commit=True)
        else:
            conn = get_db()
            conn.execute('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, contrato_id, session['user_id'], datetime.now().isoformat()))
            conn.commit()
            conn.close()
        
        flash(f'Atividade criada! OS: {numero_os}', 'success')
        return redirect('/admin/atividades')
    
    return render_template('admin_form.html', atividade=None, contratos=contratos)

@app.route('/admin/atividades/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_atividade(id):
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        atividade = execute_query("SELECT * FROM atividades WHERE id = %s", (id,), fetch_one=True)
        contratos = execute_query("SELECT * FROM contratos WHERE ativo = 1", fetch_all=True)
    else:
        conn = get_db()
        atividade = conn.execute("SELECT * FROM atividades WHERE id = ?", (id,)).fetchone()
        contratos = conn.execute("SELECT * FROM contratos WHERE ativo = 1").fetchall()
        conn.close()
        atividade = dict(atividade) if atividade else None
        contratos = [dict(c) for c in contratos] if contratos else []
    
    if not atividade:
        flash('Atividade não encontrada!', 'danger')
        return redirect('/admin/atividades')
    
    if request.method == 'POST':
        if database_url and PSYCOPG2_AVAILABLE:
            execute_query('''
                UPDATE atividades 
                SET titulo = %s, data_inicial = %s, data_final = %s, descricao = %s,
                    sistema = %s, status = %s, tipo = %s, contrato_id = %s
                WHERE id = %s
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], request.form['contrato_id'], id), commit=True)
        else:
            conn = get_db()
            conn.execute('''
                UPDATE atividades 
                SET titulo = ?, data_inicial = ?, data_final = ?, descricao = ?,
                    sistema = ?, status = ?, tipo = ?, contrato_id = ?
                WHERE id = ?
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], request.form['contrato_id'], id))
            conn.commit()
            conn.close()
        
        flash('Atividade atualizada!', 'success')
        return redirect('/admin/atividades')
    
    return render_template('admin_form.html', atividade=atividade, contratos=contratos)

@app.route('/admin/atividades/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_atividade(id):
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and PSYCOPG2_AVAILABLE:
        execute_query("DELETE FROM atividades WHERE id = %s", (id,), commit=True)
    else:
        conn = get_db()
        conn.execute("DELETE FROM atividades WHERE id = ?", (id,))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

# ============ INICIALIZAÇÃO ============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print("\n" + "="*50)
    print("🚀 Compass OS")
    print(f"📍 http://localhost:{port}")
    print("🔑 admin / Admin@2024#Seguro")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=port, debug=debug)