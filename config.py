# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-muito-segura-2024'
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'sistema_os.db')
    
    # Opções para o Metabase
    SISTEMAS = ['SDAI', 'BMS', 'SCA', 'SAI', 'Telecom']
    STATUS = ['Cancelado', 'À Fazer', 'Em Andamento', 'Concluído']
    TIPOS_ATIVIDADE = ['Manutenção Corretiva', 'Manutenção Preventiva', 'Acompanhamento', 'Outros']
    
    # Mapeamento para geração de OS
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