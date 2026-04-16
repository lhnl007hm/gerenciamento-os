# auth.py
from functools import wraps
from flask import session, redirect, url_for, flash
from database import Database

db = Database()

def login_required(f):
    """Decorator para rotas que exigem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def gerente_required(f):
    """Decorator para rotas que exigem perfil de gerente ou admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login.', 'warning')
            return redirect(url_for('login'))
        
        if session.get('role') not in ['admin', 'gerente']:
            flash('Acesso negado. Área restrita a gerentes.', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para rotas que exigem perfil de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login.', 'warning')
            return redirect(url_for('login'))
        
        if session.get('role') != 'admin':
            flash('Acesso negado. Área restrita a administradores.', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Retorna o usuário logado atualmente"""
    if 'user_id' in session:
        return db.get_usuario_by_id(session['user_id'])
    return None