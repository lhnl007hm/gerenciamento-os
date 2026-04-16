# database.py
import sqlite3
from datetime import datetime
from config import Config

class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
    
    def get_connection(self):
        """Retorna uma conexão com o banco de dados"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acesso por nome da coluna
        return conn
    
    # ============ USUÁRIOS ============
    def get_usuario_by_username(self, username):
        """Busca usuário pelo username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, senha_hash, email, nome_completo, 
                   contrato_id, role, ativo 
            FROM Usuarios 
            WHERE username = ? AND ativo = 1
        """, (username,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_usuario_by_id(self, user_id):
        """Busca usuário pelo ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, email, nome_completo, contrato_id, role 
            FROM Usuarios 
            WHERE id = ? AND ativo = 1
        """, (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_contrato_usuario(self, user_id):
        """Retorna informações do contrato do usuário"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.* 
            FROM Contratos c
            JOIN Usuarios u ON u.contrato_id = c.id
            WHERE u.id = ? AND c.ativo = 1
        """, (user_id,))
        contrato = cursor.fetchone()
        conn.close()
        return dict(contrato) if contrato else None
    
    # ============ ATIVIDADES ============
    def get_atividades_contrato(self, contrato_id, filtros=None):
        """Busca todas as atividades de um contrato"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT a.*, u.username as criado_por
            FROM Atividades a
            JOIN Usuarios u ON a.usuario_id = u.id
            WHERE a.contrato_id = ?
        """
        params = [contrato_id]
        
        if filtros:
            if filtros.get('status'):
                query += " AND a.Status = ?"
                params.append(filtros['status'])
            if filtros.get('sistema'):
                query += " AND a.Sistema = ?"
                params.append(filtros['sistema'])
        
        query += " ORDER BY a.Data_Inicial DESC"
        
        cursor.execute(query, params)
        atividades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return atividades
    
    def get_atividade_by_id(self, atividade_id, contrato_id=None):
        """Busca uma atividade específica"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM Atividades WHERE id = ?"
        params = [atividade_id]
        
        if contrato_id:
            query += " AND contrato_id = ?"
            params.append(contrato_id)
        
        cursor.execute(query, params)
        atividade = cursor.fetchone()
        conn.close()
        return dict(atividade) if atividade else None
    
    def get_proximo_numero_os(self, tipo_atividade, sistema):
        """Calcula o próximo número sequencial para OS"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM Atividades 
            WHERE Tipo_de_Atividade = ? AND Sistema = ?
        """, (tipo_atividade, sistema))
        
        result = cursor.fetchone()
        conn.close()
        return result['total'] + 1 if result else 1
    
    def insert_atividade(self, dados):
        """Insere uma nova atividade"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Atividades (
                Titulo, Data_Inicial, Data_Final, Descricao, 
                Sistema, Status, Tipo_de_Atividade, Numero_OS,
                contrato_id, usuario_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados['Titulo'],
            dados['Data_Inicial'],
            dados.get('Data_Final'),
            dados.get('Descricao'),
            dados['Sistema'],
            dados.get('Status', 'À Fazer'),
            dados['Tipo_de_Atividade'],
            dados['Numero_OS'],
            dados['contrato_id'],
            dados['usuario_id'],
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        atividade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return atividade_id
    
    def update_atividade(self, atividade_id, dados):
        """Atualiza uma atividade existente"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        campos_permitidos = [
            'Titulo', 'Data_Inicial', 'Data_Final', 'Descricao', 
            'Sistema', 'Status', 'Tipo_de_Atividade'
        ]
        
        updates = []
        valores = []
        
        for campo in campos_permitidos:
            if campo in dados:
                updates.append(f"{campo} = ?")
                valores.append(dados[campo])
        
        if updates:
            updates.append("updated_at = ?")
            valores.append(datetime.now().isoformat())
            valores.append(atividade_id)
            
            query = f"UPDATE Atividades SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, valores)
            conn.commit()
        
        conn.close()
    
    def delete_atividade(self, atividade_id):
        """Remove uma atividade"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Atividades WHERE id = ?", (atividade_id,))
        conn.commit()
        conn.close()
    
    # ============ ESTATÍSTICAS ============
    def get_estatisticas_contrato(self, contrato_id):
        """Retorna estatísticas do contrato"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_atividades,
                SUM(CASE WHEN Status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN Status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento,
                SUM(CASE WHEN Status = 'À Fazer' THEN 1 ELSE 0 END) as a_fazer,
                SUM(CASE WHEN Status = 'Cancelado' THEN 1 ELSE 0 END) as canceladas
            FROM Atividades 
            WHERE contrato_id = ?
        """, (contrato_id,))
        
        stats = dict(cursor.fetchone())
        
        # Buscar atividades recentes
        cursor.execute("""
            SELECT Titulo, Status, Data_Inicial, Sistema
            FROM Atividades 
            WHERE contrato_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (contrato_id,))
        
        stats['atividades_recentes'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return stats
    
    def get_metricas_gerenciais(self, contrato_id):
        """Retorna métricas detalhadas para gerentes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        metricas = {}
        
        # Por tipo de atividade
        cursor.execute("""
            SELECT 
                Tipo_de_Atividade,
                COUNT(*) as total,
                SUM(CASE WHEN Status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                ROUND(AVG(CASE WHEN Data_Final IS NOT NULL 
                    THEN julianday(Data_Final) - julianday(Data_Inicial)
                    ELSE NULL END), 1) as media_dias
            FROM Atividades 
            WHERE contrato_id = ?
            GROUP BY Tipo_de_Atividade
        """, (contrato_id,))
        metricas['por_tipo'] = [dict(row) for row in cursor.fetchall()]
        
        # Por sistema
        cursor.execute("""
            SELECT 
                Sistema,
                COUNT(*) as total,
                SUM(CASE WHEN Status = 'Concluído' THEN 1 ELSE 0 END) as concluidas,
                SUM(CASE WHEN Status = 'Em Andamento' THEN 1 ELSE 0 END) as em_andamento
            FROM Atividades 
            WHERE contrato_id = ?
            GROUP BY Sistema
        """, (contrato_id,))
        metricas['por_sistema'] = [dict(row) for row in cursor.fetchall()]
        
        # Timeline mensal
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', Data_Inicial) as mes,
                COUNT(*) as total,
                SUM(CASE WHEN Status = 'Concluído' THEN 1 ELSE 0 END) as concluidas
            FROM Atividades 
            WHERE contrato_id = ?
            GROUP BY strftime('%Y-%m', Data_Inicial)
            ORDER BY mes DESC
            LIMIT 6
        """, (contrato_id,))
        metricas['timeline'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return metricas