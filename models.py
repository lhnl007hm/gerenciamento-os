# models.py
from config import Config

class GeradorOS:
    """Classe responsável por gerar números de OS únicos"""
    
    def __init__(self):
        self.prefixos = Config.PREFIXOS_OS
        self.codigos_sistema = Config.CODIGOS_SISTEMA
    
    def gerar(self, tipo_atividade, sistema, proximo_numero):
        """
        Gera o código da OS no formato: MPSDAI001
        """
        prefixo = self.prefixos.get(tipo_atividade, 'OT')
        cod_sistema = self.codigos_sistema.get(sistema, 'XXX')
        
        return f"{prefixo}{cod_sistema}{proximo_numero:03d}"
    
    def validar_formato(self, numero_os):
        """Valida se o formato da OS está correto"""
        if len(numero_os) < 6:
            return False
        
        prefixo = numero_os[:2]
        sistema = numero_os[2:6] if len(numero_os) > 6 else numero_os[2:-3]
        numero = numero_os[-3:]
        
        return (prefixo in self.prefixos.values() and 
                sistema in self.codigos_sistema.values() and 
                numero.isdigit())

class ValidadorAtividade:
    """Classe para validar dados das atividades"""
    
    @staticmethod
    def validar(dados):
        erros = []
        
        # Validar título
        if not dados.get('Titulo') or len(dados['Titulo']) < 3:
            erros.append("Título deve ter pelo menos 3 caracteres")
        
        # Validar data inicial
        if not dados.get('Data_Inicial'):
            erros.append("Data inicial é obrigatória")
        
        # Validar sistema
        if dados.get('Sistema') not in Config.SISTEMAS:
            erros.append("Sistema inválido")
        
        # Validar tipo de atividade
        if dados.get('Tipo_de_Atividade') not in Config.TIPOS_ATIVIDADE:
            erros.append("Tipo de atividade inválido")
        
        # Validar status (se fornecido)
        if dados.get('Status') and dados['Status'] not in Config.STATUS:
            erros.append("Status inválido")
        
        # Validar data final (se fornecida)
        if dados.get('Data_Final') and dados.get('Data_Inicial'):
            if dados['Data_Final'] < dados['Data_Inicial']:
                erros.append("Data final não pode ser anterior à data inicial")
        
        return len(erros) == 0, erros