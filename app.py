# app.py - VERSÃO LIMPA SEM DUPLICATAS
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
import csv
import io

app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ.get('SECRET_KEY')

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
def init_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            nome TEXT,
            email TEXT,
            contrato_id INTEGER,
            role TEXT DEFAULT 'user',
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1
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
            contrato_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            created_at TEXT
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM contratos")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO contratos (nome, codigo) VALUES ('E-Business Park', 'EBP001')")
        cursor.execute("INSERT INTO contratos (nome, codigo) VALUES ('Contrato Beta', 'CT002')")
        
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('admin', '123456', 'Administrador', 'admin@compass.com.br', 1, 'admin')")
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('gerente', '123456', 'Gerente', 'gerente@compass.com.br', 1, 'gerente')")
        cursor.execute("INSERT INTO usuarios (username, senha, nome, email, contrato_id, role) VALUES ('tecnico', '123456', 'Técnico', 'tecnico@compass.com.br', 1, 'tecnico')")
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado!")

def get_db():
    conn = sqlite3.connect('instance/database.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    cursor = conn.execute('''
        SELECT COUNT(*) as total FROM atividades 
        WHERE tipo = ? AND sistema = ? AND contrato_id = ?
    ''', (tipo_atividade, sistema, contrato_id))
    
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
        
        conn = get_db()
        user = conn.execute(
            "SELECT u.*, c.nome as contrato_nome FROM usuarios u JOIN contratos c ON u.contrato_id = c.id WHERE u.username = ? AND u.senha = ?",
            (username, senha)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['nome'] = user['nome']
            session['email'] = user['email'] if user['email'] else 'master@compasss.com.br'
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
    total = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ?", (session['contrato_id'],)).fetchone()['total']
    concluidas = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Concluído'", (session['contrato_id'],)).fetchone()['total']
    andamento = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'Em Andamento'", (session['contrato_id'],)).fetchone()['total']
    afazer = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE contrato_id = ? AND status = 'À Fazer'", (session['contrato_id'],)).fetchone()['total']
    recentes = conn.execute("SELECT * FROM atividades WHERE contrato_id = ? ORDER BY id DESC LIMIT 5", (session['contrato_id'],)).fetchall()
    conn.close()
    
    return render_template('dashboard.html', total=total, concluidas=concluidas, andamento=andamento, afazer=afazer, recentes=recentes)

@app.route('/atividades')
@login_required
@admin_or_tecnico_required
def atividades():
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
    conn = get_db()
    atividade = conn.execute("SELECT * FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id'])).fetchone()
    
    if not atividade:
        conn.close()
        flash('Atividade não encontrada!', 'danger')
        return redirect('/atividades')
    
    if request.method == 'POST':
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
    conn = get_db()
    conn.execute("DELETE FROM atividades WHERE id = ? AND contrato_id = ?", (id, session['contrato_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============ MÉTRICAS ============
@app.route('/metricas')
@login_required
def metricas():
    conn = get_db()
    
    mes_filtro = request.args.get('mes', '')
    
    # Construir condição WHERE
    where_clause = "WHERE contrato_id = ?"
    params = [session['contrato_id']]
    
    if mes_filtro:
        where_clause += " AND strftime('%Y-%m', data_inicial) = ?"
        params.append(mes_filtro)
    
    # Métricas por tipo
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
    por_tipo = conn.execute(query_tipo, params).fetchall()
    
    # Métricas por sistema
    query_sistema = f'''
        SELECT sistema, COUNT(*) as total,
            SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
            SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
            SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
        FROM atividades 
        {where_clause}
        GROUP BY sistema
    '''
    por_sistema = conn.execute(query_sistema, params).fetchall()
    
    # Estatísticas gerais
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
    stats = conn.execute(query_stats, params).fetchone()
    
    # Meses disponíveis (apenas do contrato do usuário)
    meses = conn.execute('''
        SELECT DISTINCT strftime('%Y-%m', data_inicial) as mes
        FROM atividades
        WHERE contrato_id = ?
        ORDER BY mes DESC
    ''', (session['contrato_id'],)).fetchall()
    
    conn.close()
    
    # Garantir valores padrão
    if stats is None:
        stats = {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    else:
        stats = dict(stats)
    
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
    atividades = conn.execute('''
        SELECT numero_os, titulo, data_inicial, data_final, sistema, status, tipo, descricao
        FROM atividades WHERE contrato_id = ? ORDER BY data_inicial DESC
    ''', (session['contrato_id'],)).fetchall()
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
    
    # Admin vê TODOS os contratos
    total = conn.execute("SELECT COUNT(*) as total FROM atividades").fetchone()['total']
    concluidas = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Concluído'").fetchone()['total']
    andamento = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'Em Andamento'").fetchone()['total']
    afazer = conn.execute("SELECT COUNT(*) as total FROM atividades WHERE status = 'À Fazer'").fetchone()['total']
    
    # Contagem por contrato
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
    
    # Admin vê atividades de TODOS os contratos
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



@app.route('/admin/metricas')
@login_required
@admin_required
def admin_metricas():
    conn = get_db()
    
    mes_filtro = request.args.get('mes', '')
    
    # Construir condição WHERE
    where_clause = ""
    params = []
    
    if mes_filtro:
        where_clause = "WHERE strftime('%Y-%m', data_inicial) = ?"
        params.append(mes_filtro)
    
    # Métricas por tipo
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
    por_tipo = conn.execute(query_tipo, params).fetchall()
    
    # Métricas por sistema
    query_sistema = f'''
        SELECT sistema, COUNT(*) as total,
            SUM(CASE WHEN status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
            SUM(CASE WHEN status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
            SUM(CASE WHEN status = 'À Fazer' THEN 1 ELSE 0 END) as afazer
        FROM atividades 
        {where_clause}
        GROUP BY sistema
    '''
    por_sistema = conn.execute(query_sistema, params).fetchall()
    
    # Métricas por contrato
    query_contrato = f'''
        SELECT c.nome, 
            COUNT(a.id) as total,
            SUM(CASE WHEN a.status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
            SUM(CASE WHEN a.status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento
        FROM contratos c
        LEFT JOIN atividades a ON a.contrato_id = c.id
        {("AND strftime('%Y-%m', a.data_inicial) = ?" if mes_filtro else "")}
        GROUP BY c.id
        ORDER BY total DESC
    '''
    por_contrato = conn.execute(query_contrato, params if mes_filtro else []).fetchall()
    
    # Estatísticas gerais
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
    stats = conn.execute(query_stats, params).fetchone()
    
    # Meses disponíveis
    meses = conn.execute('''
        SELECT DISTINCT strftime('%Y-%m', data_inicial) as mes
        FROM atividades
        ORDER BY mes DESC
    ''').fetchall()
    
    conn.close()
    
    # Garantir valores padrão
    if stats is None:
        stats = {'total': 0, 'concluidas': 0, 'em_andamento': 0, 'afazer': 0, 'canceladas': 0, 'media_geral_dias': 0}
    else:
        stats = dict(stats)
    
    return render_template('admin_metricas.html',
                         por_tipo=por_tipo,
                         por_sistema=por_sistema,
                         por_contrato=por_contrato,
                         stats=stats,
                         meses=meses,
                         mes_selecionado=mes_filtro)

# ============ ADMIN - ATIVIDADES ============

@app.route('/admin/atividades/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_nova_atividade():
    conn = get_db()
    contratos = conn.execute("SELECT * FROM contratos WHERE ativo = 1").fetchall()
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        data_inicial = request.form['data_inicial']
        data_final = request.form.get('data_final', '')
        descricao = request.form.get('descricao', '')
        sistema = request.form['sistema']
        status = request.form['status']
        tipo = request.form['tipo']
        contrato_id = request.form['contrato_id']  # Admin escolhe o contrato
        
        numero_os = gerar_numero_os(tipo, sistema, contrato_id)
        
        conn.execute('''
            INSERT INTO atividades 
            (titulo, data_inicial, data_final, descricao, sistema, status, tipo, 
             numero_os, contrato_id, usuario_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            titulo, data_inicial, data_final if data_final else None, descricao,
            sistema, status, tipo, numero_os, contrato_id, 
            session['user_id'], datetime.now().isoformat()
        ))
        
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
    atividade = conn.execute("SELECT * FROM atividades WHERE id = ?", (id,)).fetchone()
    contratos = conn.execute("SELECT * FROM contratos WHERE ativo = 1").fetchall()
    
    if not atividade:
        conn.close()
        flash('Atividade não encontrada!', 'danger')
        return redirect('/admin/atividades')
    
    if request.method == 'POST':
        conn.execute('''
            UPDATE atividades 
            SET titulo = ?, data_inicial = ?, data_final = ?, descricao = ?,
                sistema = ?, status = ?, tipo = ?, contrato_id = ?
            WHERE id = ?
        ''', (
            request.form['titulo'],
            request.form['data_inicial'],
            request.form.get('data_final') or None,
            request.form.get('descricao'),
            request.form['sistema'],
            request.form['status'],
            request.form['tipo'],
            request.form['contrato_id'],
            id
        ))
        
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
    conn.execute(
        "DELETE FROM atividades WHERE id = ? AND contrato_id = ?",
        (id, session['contrato_id'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============ ADMIN - USUÁRIOS (CORRIGIDO) ============
@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    conn = get_db()
    usuarios = conn.execute("""
        SELECT u.*, c.nome as contrato_nome 
        FROM usuarios u 
        LEFT JOIN contratos c ON u.contrato_id = c.id 
        ORDER BY u.id
    """).fetchall()
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_novo_usuario():
    conn = get_db()
    contratos = conn.execute("SELECT * FROM contratos").fetchall()
    
    if request.method == 'POST':
        username = request.form['username']
        senha = request.form['senha']
        nome = request.form['nome']
        email = request.form.get('email', '')
        contrato_id = request.form['contrato_id']
        role = request.form['role']
        
        try:
            # Verificar se as colunas existem
            cursor = conn.execute("PRAGMA table_info(usuarios)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if 'email' in colunas and 'ativo' in colunas:
                conn.execute('''
                    INSERT INTO usuarios (username, senha, nome, email, contrato_id, role, ativo)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (username, senha, nome, email, contrato_id, role))
            else:
                conn.execute('''
                    INSERT INTO usuarios (username, senha, nome, contrato_id, role)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, senha, nome, contrato_id, role))
            
            conn.commit()
            flash('Usuário criado com sucesso!', 'success')
        except sqlite3.IntegrityError as e:
            flash(f'Erro: Nome de usuário já existe! ({str(e)})', 'danger')
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
    usuario = conn.execute("SELECT * FROM usuarios WHERE id = ?", (id,)).fetchone()
    contratos = conn.execute("SELECT * FROM contratos").fetchall()
    
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
            
            # Verificar colunas existentes
            cursor = conn.execute("PRAGMA table_info(usuarios)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if request.form.get('senha'):
                if 'email' in colunas and 'ativo' in colunas:
                    conn.execute('''
                        UPDATE usuarios 
                        SET nome = ?, email = ?, contrato_id = ?, role = ?, ativo = ?, senha = ?
                        WHERE id = ?
                    ''', (nome, email, contrato_id, role, ativo, request.form['senha'], id))
                else:
                    conn.execute('''
                        UPDATE usuarios 
                        SET nome = ?, contrato_id = ?, role = ?, senha = ?
                        WHERE id = ?
                    ''', (nome, contrato_id, role, request.form['senha'], id))
            else:
                if 'email' in colunas and 'ativo' in colunas:
                    conn.execute('''
                        UPDATE usuarios 
                        SET nome = ?, email = ?, contrato_id = ?, role = ?, ativo = ?
                        WHERE id = ?
                    ''', (nome, email, contrato_id, role, ativo, id))
                else:
                    conn.execute('''
                        UPDATE usuarios 
                        SET nome = ?, contrato_id = ?, role = ?
                        WHERE id = ?
                    ''', (nome, contrato_id, role, id))
            
            conn.commit()
            flash('Usuário atualizado!', 'success')
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/usuarios')
    
    # Garantir valores padrão
    usuario_dict = dict(usuario)
    if 'email' not in usuario_dict:
        usuario_dict['email'] = ''
    if 'ativo' not in usuario_dict:
        usuario_dict['ativo'] = 1
    
    conn.close()
    return render_template('admin_usuario_form.html', usuario=usuario_dict, contratos=contratos)

@app.route('/admin/usuarios/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_usuario(id):
    if id == session['user_id']:
        return jsonify({'success': False, 'error': 'Não pode excluir seu próprio usuário!'})
    
    conn = get_db()
    conn.execute("DELETE FROM usuarios WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============ ADMIN - CONTRATOS (CORRIGIDO) ============
@app.route('/admin/contratos')
@login_required
@admin_required
def admin_contratos():
    conn = get_db()
    contratos = conn.execute("SELECT * FROM contratos ORDER BY id").fetchall()
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
        try:
            # Verificar colunas
            cursor = conn.execute("PRAGMA table_info(contratos)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if 'ativo' in colunas:
                conn.execute(
                    "INSERT INTO contratos (nome, codigo, ativo) VALUES (?, ?, 1)",
                    (nome, codigo)
                )
            else:
                conn.execute(
                    "INSERT INTO contratos (nome, codigo) VALUES (?, ?)",
                    (nome, codigo)
                )
            
            conn.commit()
            flash('Contrato criado com sucesso!', 'success')
        except sqlite3.IntegrityError:
            flash('Erro: Código do contrato já existe!', 'danger')
        except Exception as e:
            flash(f'Erro ao criar contrato: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/contratos')
    
    return render_template('admin_contrato_form.html', contrato=None)

@app.route('/admin/contratos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_contrato(id):
    conn = get_db()
    contrato = conn.execute("SELECT * FROM contratos WHERE id = ?", (id,)).fetchone()
    
    if not contrato:
        conn.close()
        flash('Contrato não encontrado!', 'danger')
        return redirect('/admin/contratos')
    
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            codigo = request.form['codigo']
            ativo = 1 if request.form.get('ativo') else 0
            
            # Verificar colunas
            cursor = conn.execute("PRAGMA table_info(contratos)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            if 'ativo' in colunas:
                conn.execute(
                    "UPDATE contratos SET nome = ?, codigo = ?, ativo = ? WHERE id = ?",
                    (nome, codigo, ativo, id)
                )
            else:
                conn.execute(
                    "UPDATE contratos SET nome = ?, codigo = ? WHERE id = ?",
                    (nome, codigo, id)
                )
            
            conn.commit()
            flash('Contrato atualizado!', 'success')
        except sqlite3.IntegrityError:
            flash('Erro: Código do contrato já existe!', 'danger')
        except Exception as e:
            flash(f'Erro ao atualizar: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect('/admin/contratos')
    
    # Garantir valor padrão para ativo
    contrato_dict = dict(contrato)
    if 'ativo' not in contrato_dict:
        contrato_dict['ativo'] = 1
    
    conn.close()
    return render_template('admin_contrato_form.html', contrato=contrato_dict)

@app.route('/admin/contratos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_excluir_contrato(id):
    conn = get_db()
    
    usuarios = conn.execute("SELECT COUNT(*) as total FROM usuarios WHERE contrato_id = ?", (id,)).fetchone()
    
    if usuarios['total'] > 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Existem usuários vinculados a este contrato!'})
    
    conn.execute("DELETE FROM contratos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ============ INICIALIZAÇÃO ============
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)

# Exportar para Vercel
app = app