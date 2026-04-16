# app.py - VERSÃO COMPLETA E CORRIGIDA
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
import csv
import io

# Tenta importar PostgreSQL (opcional)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️ PostgreSQL não disponível, usando SQLite")

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

def get_sqlite_connection():
    """Retorna conexão SQLite"""
    if not os.path.exists('instance'):
        os.makedirs('instance')
    conn = sqlite3.connect('instance/database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_db():
    """Retorna conexão com o banco (PostgreSQL ou SQLite)"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # PostgreSQL (produção)
        try:
            result = urlparse(database_url)
            conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                sslmode='require',
                connect_timeout=10
            )
            print("✅ Conectado ao PostgreSQL (Session Pooler)")
            return conn
        except Exception as e:
            print(f"❌ Erro PostgreSQL: {e}")
            # Na Vercel, NÃO tente SQLite
            if os.environ.get('VERCEL'):
                raise e
            # Localmente, fallback para SQLite
            return get_sqlite_connection()
    else:
        # SQLite (desenvolvimento local)
        return get_sqlite_connection()

def init_db():
    """Inicializa o banco de dados"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Na Vercel, NÃO tente criar SQLite (sistema de arquivos é somente leitura)
    if os.environ.get('VERCEL'):
        print("✅ Vercel detectada - usando PostgreSQL (tabelas já criadas no Supabase)")
        return
    
    if database_url and POSTGRES_AVAILABLE:
        print("✅ Usando PostgreSQL (produção) - tabelas já devem existir")
        return
    
    # SQLite - APENAS desenvolvimento local
    print("✅ Usando SQLite (desenvolvimento local)")
    
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    
    # Cria tabelas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
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
    
    cursor.execute('''
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
    
    # Dados iniciais
    cursor.execute("SELECT COUNT(*) FROM contratos")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO contratos (nome, codigo) VALUES ('E-Business Park', 'EBP001')")
        cursor.execute("INSERT INTO contratos (nome, codigo) VALUES ('Contrato Beta', 'CT002')")
        
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('admin', 'admin123', 'Administrador', 'admin@compass.com.br', 1, 'admin')")
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('gerente', 'gerente123', 'Gerente', 'gerente@compass.com.br', 1, 'gerente')")
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('tecnico', 'tecnico123', 'Técnico', 'tecnico@compass.com.br', 1, 'tecnico')")
        
        print("✅ Dados iniciais inseridos!")
    
    conn.commit()
    conn.close()
    print("✅ Banco SQLite inicializado!")
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
    
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE tipo = %s AND sistema = %s AND contrato_id = %s", (tipo_atividade, sistema, contrato_id))
        count = cur.fetchone()[0] + 1
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE tipo = ? AND sistema = ? AND contrato_id = ?", (tipo_atividade, sistema, contrato_id))
        count = cur.fetchone()[0] + 1
    
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
        
        conn = get_db()
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and POSTGRES_AVAILABLE:
            cur = conn.cursor()
            cur.execute("SELECT u.*, c.nome as contrato_nome FROM usuarios u JOIN contratos c ON u.contrato_id = c.id WHERE u.username = %s AND u.senha = %s", (username, senha))
            row = cur.fetchone()
            
            if row:
                # Converter manualmente para dicionário
                colnames = [desc[0] for desc in cur.description]
                user = dict(zip(colnames, row))
            else:
                user = None
            cur.close()
        else:
            cur = conn.cursor()
            cur.execute("SELECT u.*, c.nome as contrato_nome FROM usuarios u JOIN contratos c ON u.contrato_id = c.id WHERE u.username = ? AND u.senha = ?", (username, senha))
            row = cur.fetchone()
            if row:
                user = dict(row)
            else:
                user = None
        
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nome'] = user['nome']
            session['email'] = user.get('email') if user.get('email') else 'master@compass.com.br'
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
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s", (session['contrato_id'],))
        total = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'Concluído'", (session['contrato_id'],))
        concluidas = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'Em Andamento'", (session['contrato_id'],))
        andamento = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = %s AND status = 'À Fazer'", (session['contrato_id'],))
        afazer = cur.fetchone()['total']
        cur.execute("SELECT * FROM atividades WHERE contrato_id = %s ORDER BY id DESC LIMIT 5", (session['contrato_id'],))
        recentes = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ?", (session['contrato_id'],))
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Concluído'", (session['contrato_id'],))
        concluidas = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Em Andamento'", (session['contrato_id'],))
        andamento = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'À Fazer'", (session['contrato_id'],))
        afazer = cur.fetchone()[0]
        cur.execute("SELECT * FROM atividades WHERE contrato_id = ? ORDER BY id DESC LIMIT 5", (session['contrato_id'],))
        recentes = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    return render_template('dashboard.html', total=total, concluidas=concluidas, andamento=andamento, afazer=afazer, recentes=recentes)

@app.route('/atividades')
@login_required
@admin_or_tecnico_required
def atividades():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.contrato_id = %s
            ORDER BY a.id DESC
        """, (session['contrato_id'],))
        atividades = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            WHERE a.contrato_id = ?
            ORDER BY a.id DESC
        """, (session['contrato_id'],))
        atividades = [dict(row) for row in cur.fetchall()]
    
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
        
        conn = get_db()
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and POSTGRES_AVAILABLE:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, session['contrato_id'], session['user_id'], datetime.now().isoformat()))
            conn.commit()
            cur.close()
        else:
            cur = conn.cursor()
            cur.execute('''
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
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM atividades WHERE id = %s AND contrato_id = %s", (id, session['contrato_id']))
        atividade = cur.fetchone()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id']))
        row = cur.fetchone()
        atividade = dict(row) if row else None
    
    if not atividade:
        conn.close()
        flash('Atividade não encontrada!', 'danger')
        return redirect('/atividades')
    
    if request.method == 'POST':
        if database_url and POSTGRES_AVAILABLE:
            cur = conn.cursor()
            cur.execute('''
                UPDATE atividades 
                SET titulo = %s, data_inicial = %s, data_final = %s, descricao = %s, sistema = %s, status = %s, tipo = %s
                WHERE id = %s
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], id))
            conn.commit()
            cur.close()
        else:
            cur = conn.cursor()
            cur.execute('''
                UPDATE atividades 
                SET titulo = ?, data_inicial = ?, data_final = ?, descricao = ?, sistema = ?, status = ?, tipo = ?
                WHERE id = ?
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], id))
            conn.commit()
        
        conn.close()
        flash('Atividade atualizada!', 'success')
        return redirect('/atividades')
    
    conn.close()
    return render_template('form.html', atividade=atividade)

@app.route('/atividades/<int:id>/excluir', methods=['POST'])
@login_required
@admin_or_tecnico_required
def excluir_atividade(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("DELETE FROM atividades WHERE id = %s AND contrato_id = %s", (id, session['contrato_id']))
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("DELETE FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id']))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

# ============ MÉTRICAS ============
@app.route('/metricas')
@login_required
def metricas():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    mes_filtro = request.args.get('mes', '')
    
    if database_url and POSTGRES_AVAILABLE:
        # PostgreSQL
        cur = conn.cursor()
        
        # Métricas por tipo
        query_tipo = '''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::timestamp - data_inicial::timestamp))/86400 ELSE NULL END), 1) as media_dias
            FROM atividades 
            WHERE contrato_id = %s
        '''
        params_tipo = [session['contrato_id']]
        
        if mes_filtro:
            query_tipo += " AND TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_tipo.append(mes_filtro)
        
        query_tipo += " GROUP BY tipo"
        cur.execute(query_tipo, params_tipo)
        por_tipo = cur.fetchall()
        
        # Métricas por sistema
        query_sistema = '''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades 
            WHERE contrato_id = %s
        '''
        params_sistema = [session['contrato_id']]
        
        if mes_filtro:
            query_sistema += " AND TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_sistema.append(mes_filtro)
        
        query_sistema += " GROUP BY sistema"
        cur.execute(query_sistema, params_sistema)
        por_sistema = cur.fetchall()
        
        # Estatísticas gerais
        query_stats = '''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::timestamp - data_inicial::timestamp))/86400 ELSE NULL END), 1) as media_geral_dias
            FROM atividades
            WHERE contrato_id = %s
        '''
        params_stats = [session['contrato_id']]
        
        if mes_filtro:
            query_stats += " AND TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_stats.append(mes_filtro)
        
        cur.execute(query_stats, params_stats)
        stats = cur.fetchone()
        
        # Meses disponíveis
        cur.execute('''
            SELECT DISTINCT TO_CHAR(data_inicial, 'YYYY-MM') as mes
            FROM atividades
            WHERE contrato_id = %s
            ORDER BY mes DESC
        ''', (session['contrato_id'],))
        meses = cur.fetchall()
        
        cur.close()
    else:
        # SQLite
        cur = conn.cursor()
        
        where_clause = "WHERE contrato_id = ?"
        params = [session['contrato_id']]
        
        if mes_filtro:
            where_clause += " AND strftime('%Y-%m', data_inicial) = ?"
            params.append(mes_filtro)
        
        query_tipo = f'''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_dias
            FROM atividades 
            {where_clause}
            GROUP BY tipo
        '''
        cur.execute(query_tipo, params)
        por_tipo = [dict(row) for row in cur.fetchall()]
        
        query_sistema = f'''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades 
            {where_clause}
            GROUP BY sistema
        '''
        cur.execute(query_sistema, params)
        por_sistema = [dict(row) for row in cur.fetchall()]
        
        query_stats = f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_geral_dias
            FROM atividades
            {where_clause}
        '''
        cur.execute(query_stats, params)
        stats_row = cur.fetchone()
        stats = dict(stats_row) if stats_row else {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
        
        cur.execute('''
            SELECT DISTINCT strftime('%Y-%m', data_inicial) as mes
            FROM atividades
            WHERE contrato_id = ?
            ORDER BY mes DESC
        ''', (session['contrato_id'],))
        meses = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    if stats is None:
        stats = {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    
    return render_template('metricas.html', 
                         por_tipo=por_tipo, 
                         por_sistema=por_sistema, 
                         stats=stats,
                         meses=meses,
                         mes_selecionado=mes_filtro)

@app.route('/metricas/exportar')
@login_required
def exportar_relatorio():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute('''
            SELECT numero_os, titulo, TO_CHAR(data_inicial, 'DD/MM/YYYY') as data_inicial, 
                   TO_CHAR(data_final, 'DD/MM/YYYY') as data_final, sistema, status, tipo, descricao
            FROM atividades WHERE contrato_id = %s ORDER BY data_inicial DESC
        ''', (session['contrato_id'],))
        atividades = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute('''
            SELECT numero_os, titulo, data_inicial, data_final, sistema, status, tipo, descricao
            FROM atividades WHERE contrato_id = ? ORDER BY data_inicial DESC
        ''', (session['contrato_id'],))
        atividades = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
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

# ============ ADMIN - VISÃO GLOBAL ============
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades")
        total = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Concluído'")
        concluidas = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Em Andamento'")
        andamento = cur.fetchone()['total']
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'À Fazer'")
        afazer = cur.fetchone()['total']
        
        cur.execute("""
            SELECT c.nome, COUNT(a.id) as total
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
            GROUP BY c.id
            ORDER BY total DESC
        """)
        por_contrato = cur.fetchall()
        
        cur.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC LIMIT 10
        """)
        recentes = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM atividades")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Concluído'")
        concluidas = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Em Andamento'")
        andamento = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'À Fazer'")
        afazer = cur.fetchone()[0]
        
        cur.execute("""
            SELECT c.nome, COUNT(a.id) as total
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
            GROUP BY c.id
            ORDER BY total DESC
        """)
        por_contrato = [dict(row) for row in cur.fetchall()]
        
        cur.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC LIMIT 10
        """)
        recentes = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total=total, 
                         concluidas=concluidas, 
                         andamento=andamento,
                         afazer=afazer,
                         por_contrato=por_contrato,
                         recentes=recentes)

@app.route('/admin/atividades')
@login_required
@admin_required
def admin_atividades():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN contratos c ON a.contrato_id = c.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC
        """)
        atividades = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, c.nome as contrato_nome, u.nome as criado_por 
            FROM atividades a
            LEFT JOIN contratos c ON a.contrato_id = c.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.id DESC
        """)
        atividades = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return render_template('admin_atividades.html', atividades=atividades)

@app.route('/admin/metricas')
@login_required
@admin_required
def admin_metricas():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    mes_filtro = request.args.get('mes', '')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        
        query_tipo = '''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::timestamp - data_inicial::timestamp))/86400 ELSE NULL END), 1) as media_dias
            FROM atividades
        '''
        params_tipo = []
        if mes_filtro:
            query_tipo += " WHERE TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_tipo.append(mes_filtro)
        query_tipo += " GROUP BY tipo"
        cur.execute(query_tipo, params_tipo)
        por_tipo = cur.fetchall()
        
        query_sistema = '''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades
        '''
        params_sistema = []
        if mes_filtro:
            query_sistema += " WHERE TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_sistema.append(mes_filtro)
        query_sistema += " GROUP BY sistema"
        cur.execute(query_sistema, params_sistema)
        por_sistema = cur.fetchall()
        
        query_contrato = '''
            SELECT c.nome, 
                COUNT(a.id) as total,
                SUM(CASE WHEN a.status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN a.status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
        '''
        params_contrato = []
        if mes_filtro:
            query_contrato += " AND TO_CHAR(a.data_inicial, 'YYYY-MM') = %s"
            params_contrato.append(mes_filtro)
        query_contrato += " GROUP BY c.id ORDER BY total DESC"
        cur.execute(query_contrato, params_contrato)
        por_contrato = cur.fetchall()
        
        query_stats = '''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN EXTRACT(EPOCH FROM (data_final::timestamp - data_inicial::timestamp))/86400 ELSE NULL END), 1) as media_geral_dias
            FROM atividades
        '''
        params_stats = []
        if mes_filtro:
            query_stats += " WHERE TO_CHAR(data_inicial, 'YYYY-MM') = %s"
            params_stats.append(mes_filtro)
        cur.execute(query_stats, params_stats)
        stats = cur.fetchone()
        
        cur.execute("SELECT DISTINCT TO_CHAR(data_inicial, 'YYYY-MM') as mes FROM atividades ORDER BY mes DESC")
        meses = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        
        where_clause = ""
        params = []
        if mes_filtro:
            where_clause = "WHERE strftime('%Y-%m', data_inicial) = ?"
            params.append(mes_filtro)
        
        query_tipo = f'''
            SELECT tipo, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_dias
            FROM atividades 
            {where_clause}
            GROUP BY tipo
        '''
        cur.execute(query_tipo, params)
        por_tipo = [dict(row) for row in cur.fetchall()]
        
        query_sistema = f'''
            SELECT sistema, COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
            FROM atividades 
            {where_clause}
            GROUP BY sistema
        '''
        cur.execute(query_sistema, params)
        por_sistema = [dict(row) for row in cur.fetchall()]
        
        query_contrato = f'''
            SELECT c.nome, 
                COUNT(a.id) as total,
                SUM(CASE WHEN a.status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN a.status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento
            FROM contratos c
            LEFT JOIN atividades a ON a.contrato_id = c.id
            {("WHERE strftime('%Y-%m', a.data_inicial) = ?" if mes_filtro else "")}
            GROUP BY c.id
            ORDER BY total DESC
        '''
        cur.execute(query_contrato, params if mes_filtro else [])
        por_contrato = [dict(row) for row in cur.fetchall()]
        
        query_stats = f'''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer,
                SUM(CASE WHEN status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas,
                ROUND(AVG(CASE WHEN data_final IS NOT NULL THEN julianday(data_final) - julianday(data_inicial) ELSE NULL END), 1) as media_geral_dias
            FROM atividades
            {where_clause}
        '''
        cur.execute(query_stats, params)
        stats_row = cur.fetchone()
        stats = dict(stats_row) if stats_row else {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
        
        cur.execute("SELECT DISTINCT strftime('%Y-%m', data_inicial) as mes FROM atividades ORDER BY mes DESC")
        meses = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    if stats is None:
        stats = {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    
    return render_template('admin_metricas.html',
                         por_tipo=por_tipo,
                         por_sistema=por_sistema,
                         por_contrato=por_contrato,
                         stats=stats,
                         meses=meses,
                         mes_selecionado=mes_filtro)

@app.route('/admin/metricas/exportar')
@login_required
@admin_required
def admin_exportar_relatorio():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute('''
            SELECT a.numero_os, a.titulo, 
                   TO_CHAR(a.data_inicial, 'DD/MM/YYYY') as data_inicial,
                   TO_CHAR(a.data_final, 'DD/MM/YYYY') as data_final,
                   a.sistema, a.status, a.tipo, a.descricao,
                   c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.data_inicial DESC
        ''')
        atividades = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute('''
            SELECT a.numero_os, a.titulo, a.data_inicial, a.data_final,
                   a.sistema, a.status, a.tipo, a.descricao,
                   c.nome as contrato_nome, u.nome as criado_por
            FROM atividades a
            JOIN contratos c ON a.contrato_id = c.id
            JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY a.data_inicial DESC
        ''')
        atividades = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['RELATÓRIO ADMIN - TODOS OS CONTRATOS'])
    writer.writerow(['Gerado em: ' + datetime.now().strftime('%d/%m/%Y %H:%M')])
    writer.writerow([])
    writer.writerow(['Número OS', 'Título', 'Data Inicial', 'Data Final', 'Sistema', 'Status', 'Tipo', 'Contrato', 'Criado por'])
    
    for a in atividades:
        writer.writerow([
            a['numero_os'], 
            a['titulo'], 
            a['data_inicial'], 
            a['data_final'] or '-', 
            a['sistema'], 
            a['status'], 
            a['tipo'],
            a['contrato_nome'],
            a['criado_por']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')), 
        mimetype='text/csv', 
        as_attachment=True, 
        download_name=f'relatorio_admin_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    )

# ============ ADMIN - ATIVIDADES ============
@app.route('/admin/atividades/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_nova_atividade():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos WHERE ativo = 1")
        contratos = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos WHERE ativo = 1")
        contratos = [dict(row) for row in cur.fetchall()]
    
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
        
        if database_url and POSTGRES_AVAILABLE:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, contrato_id, session['user_id'], datetime.now().isoformat()))
            conn.commit()
            cur.close()
        else:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO atividades 
                (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
                 numero_os, contrato_id, usuario_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (titulo, data_inicial, data_final if data_final else None, descricao, sistema, status, tipo, numero_os, contrato_id, session['user_id'], datetime.now().isoformat()))
            conn.commit()
        
        conn.close()
        flash(f'Atividade criada! OS: {numero_os}', 'success')
        return redirect('/admin/atividades')
    
    conn.close()
    return render_template('admin_form.html', atividade=None, contratos=contratos)

@app.route('/admin/atividades/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_atividade(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM atividades WHERE id = %s", (id,))
        atividade = cur.fetchone()
        cur.execute("SELECT * FROM contratos WHERE ativo = 1")
        contratos = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM atividades WHERE id = ?", (id,))
        row = cur.fetchone()
        atividade = dict(row) if row else None
        cur.execute("SELECT * FROM contratos WHERE ativo = 1")
        contratos = [dict(row) for row in cur.fetchall()]
    
    if not atividade:
        conn.close()
        flash('Atividade não encontrada!', 'danger')
        return redirect('/admin/atividades')
    
    if request.method == 'POST':
        if database_url and POSTGRES_AVAILABLE:
            cur = conn.cursor()
            cur.execute('''
                UPDATE atividades 
                SET titulo = %s, data_inicial = %s, data_final = %s, descricao = %s,
                    sistema = %s, status = %s, tipo = %s, contrato_id = %s
                WHERE id = %s
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], request.form['contrato_id'], id))
            conn.commit()
            cur.close()
        else:
            cur = conn.cursor()
            cur.execute('''
                UPDATE atividades 
                SET titulo = ?, data_inicial = ?, data_final = ?, descricao = ?,
                    sistema = ?, status = ?, tipo = ?, contrato_id = ?
                WHERE id = ?
            ''', (request.form['titulo'], request.form['data_inicial'], request.form.get('data_final') or None, request.form.get('descricao'), request.form['sistema'], request.form['status'], request.form['tipo'], request.form['contrato_id'], id))
            conn.commit()
        
        conn.close()
        flash('Atividade atualizada!', 'success')
        return redirect('/admin/atividades')
    
    conn.close()
    return render_template('admin_form.html', atividade=atividade, contratos=contratos)

@app.route('/admin/atividades/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_atividade(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("DELETE FROM atividades WHERE id = %s", (id,))
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("DELETE FROM atividades WHERE id = ?", (id,))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

# ============ ADMIN - USUÁRIOS ============
@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.*, c.nome as contrato_nome 
            FROM usuarios u 
            LEFT JOIN contratos c ON u.contrato_id = c.id 
            ORDER BY u.id
        """)
        usuarios = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.*, c.nome as contrato_nome 
            FROM usuarios u 
            LEFT JOIN contratos c ON u.contrato_id = c.id 
            ORDER BY u.id
        """)
        usuarios = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_novo_usuario():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos")
        contratos = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos")
        contratos = [dict(row) for row in cur.fetchall()]
    
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        nome = request.form['nome']
        email = request.form.get('email', '')
        contrato_id = request.form['contrato_id']
        role = request.form['role']
        
        try:
            if database_url and POSTGRES_AVAILABLE:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO usuarios (username, senha, nome, email, contrato_id, role, ativo)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                ''', (username, senha, nome, email, contrato_id, role))
                conn.commit()
                cur.close()
            else:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO usuarios (username, senha, nome, email, contrato_id, role, ativo)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (username, senha, nome, email, contrato_id, role))
                conn.commit()
            
            flash('Usuário criado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro ao criar usuário: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/usuarios')
    
    conn.close()
    return render_template('admin_usuario_form.html', usuario=None, contratos=contratos)

@app.route('/admin/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_usuario(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
        usuario = cur.fetchone()
        cur.execute("SELECT * FROM contratos")
        contratos = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE id = ?", (id,))
        row = cur.fetchone()
        usuario = dict(row) if row else None
        cur.execute("SELECT * FROM contratos")
        contratos = [dict(row) for row in cur.fetchall()]
    
    if not usuario:
        conn.close()
        flash('Usuário não encontrado!', 'danger')
        return redirect('/admin/usuarios')
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            email = request.form.get('email', '')
            contrato_id = request.form['contrato_id']
            role = request.form['role']
            ativo = 1 if request.form.get('ativo') else 0
            
            if request.form.get('senha'):
                if database_url and POSTGRES_AVAILABLE:
                    cur = conn.cursor()
                    cur.execute('''
                        UPDATE usuarios 
                        SET nome = %s, email = %s, contrato_id = %s, role = %s, ativo = %s, senha = %s
                        WHERE id = %s
                    ''', (nome, email, contrato_id, role, ativo, request.form['senha'], id))
                    conn.commit()
                    cur.close()
                else:
                    cur = conn.cursor()
                    cur.execute('''
                        UPDATE usuarios 
                        SET nome = ?, email = ?, contrato_id = ?, role = ?, ativo = ?, senha = ?
                        WHERE id = ?
                    ''', (nome, email, contrato_id, role, ativo, request.form['senha'], id))
                    conn.commit()
            else:
                if database_url and POSTGRES_AVAILABLE:
                    cur = conn.cursor()
                    cur.execute('''
                        UPDATE usuarios 
                        SET nome = %s, email = %s, contrato_id = %s, role = %s, ativo = %s
                        WHERE id = %s
                    ''', (nome, email, contrato_id, role, ativo, id))
                    conn.commit()
                    cur.close()
                else:
                    cur = conn.cursor()
                    cur.execute('''
                        UPDATE usuarios 
                        SET nome = ?, email = ?, contrato_id = ?, role = ?, ativo = ?
                        WHERE id = ?
                    ''', (nome, email, contrato_id, role, ativo, id))
                    conn.commit()
            
            flash('Usuário atualizado!', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/usuarios')
    
    conn.close()
    return render_template('admin_usuario_form.html', usuario=usuario, contratos=contratos)

@app.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_usuario(id):
    if id == session['user_id']:
        return jsonify({'success': False, 'error': 'Não pode excluir seu próprio usuário!'})
    
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE id = %s", (id,))
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("DELETE FROM usuarios WHERE id = ?", (id,))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

# ============ ADMIN - CONTRATOS ============
@app.route('/admin/contratos')
@login_required
@admin_required
def admin_contratos():
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos ORDER BY id")
        contratos = cur.fetchall()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos ORDER BY id")
        contratos = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    return render_template('admin_contratos.html', contratos=contratos)

@app.route('/admin/contratos/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_novo_contrato():
    if request.method == 'POST':
        nome = request.form['nome']
        codigo = request.form['codigo']
        
        conn = get_db()
        database_url = os.environ.get('DATABASE_URL')
        
        try:
            if database_url and POSTGRES_AVAILABLE:
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (nome, codigo, ativo) VALUES (%s, %s, 1)", (nome, codigo))
                conn.commit()
                cur.close()
            else:
                cur = conn.cursor()
                cur.execute("INSERT INTO contratos (nome, codigo, ativo) VALUES (?, ?, 1)", (nome, codigo))
                conn.commit()
            
            flash('Contrato criado com sucesso!', 'success')
        except Exception as e:
            flash(f'Erro: Código do contrato já existe! ({str(e)})', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/contratos')
    
    return render_template('admin_contrato_form.html', contrato=None)

@app.route('/admin/contratos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_contrato(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos WHERE id = %s", (id,))
        contrato = cur.fetchone()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contratos WHERE id = ?", (id,))
        row = cur.fetchone()
        contrato = dict(row) if row else None
    
    if not contrato:
        conn.close()
        flash('Contrato não encontrado!', 'danger')
        return redirect('/admin/contratos')
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            codigo = request.form['codigo']
            ativo = 1 if request.form.get('ativo') else 0
            
            if database_url and POSTGRES_AVAILABLE:
                cur = conn.cursor()
                cur.execute("UPDATE contratos SET nome = %s, codigo = %s, ativo = %s WHERE id = %s", (nome, codigo, ativo, id))
                conn.commit()
                cur.close()
            else:
                cur = conn.cursor()
                cur.execute("UPDATE contratos SET nome = ?, codigo = ?, ativo = ? WHERE id = ?", (nome, codigo, ativo, id))
                conn.commit()
            
            flash('Contrato atualizado!', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/contratos')
    
    conn.close()
    return render_template('admin_contrato_form.html', contrato=contrato)

@app.route('/admin/contratos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_contrato(id):
    conn = get_db()
    database_url = os.environ.get('DATABASE_URL')
    
    # Verificar se tem usuários
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM usuarios WHERE contrato_id = %s", (id,))
        usuarios = cur.fetchone()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM usuarios WHERE contrato_id = ?", (id,))
        usuarios = {'total': cur.fetchone()[0]}
    
    if usuarios['total'] > 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Existem usuários vinculados a este contrato!'})
    
    if database_url and POSTGRES_AVAILABLE:
        cur = conn.cursor()
        cur.execute("DELETE FROM contratos WHERE id = %s", (id,))
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute("DELETE FROM contratos WHERE id = ?", (id,))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

# ============ INICIALIZAÇÃO ============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)