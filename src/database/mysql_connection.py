"""
Módulo de conexão com MySQL
"""
import os
import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import streamlit as st

# Carrega variáveis de ambiente
load_dotenv()


class MySQLConnection:
    """Classe para gerenciar conexões com MySQL"""
    
    def __init__(self):
        self.host = os.getenv('MYSQL_HOST')
        self.port = int(os.getenv('MYSQL_PORT', 3306))
        self.database = os.getenv('MYSQL_DB')
        self.user = os.getenv('MYSQL_USER')
        self.password = os.getenv('MYSQL_PASSWORD')
        self.engine = None
    
    def get_connection(self):
        """Retorna uma nova conexão PyMySQL.

        Conexões PyMySQL não devem ficar cacheadas no Streamlit: o MySQL pode
        fechar a sessão por timeout e o driver passa a retornar InterfaceError(0, "").
        """
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30
            )
            return connection
        except Exception as e:
            st.error(f"Erro ao conectar ao MySQL: {e}")
            return None
    
    @st.cache_resource
    def get_engine(_self):
        """Retorna um engine SQLAlchemy"""
        try:
            connection_url = URL.create(
                "mysql+pymysql",
                username=_self.user,
                password=_self.password,
                host=_self.host,
                port=_self.port,
                database=_self.database
            )
            engine = create_engine(
                connection_url,
                pool_pre_ping=True,
                pool_recycle=1800
            )
            _self.engine = engine
            return engine
        except Exception as e:
            st.error(f"Erro ao criar engine SQLAlchemy: {e}")
            return None
    
    def execute_query(self, query, params=None):
        """Executa uma query e retorna os resultados"""
        connection = self.get_connection()
        if not connection:
            return None
        
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params or ())
                    result = cursor.fetchall()
            return result
        except Exception as e:
            st.error(f"Erro ao executar query: {e}")
            return None
    
    def execute_update(self, query, params=None):
        """Executa uma query de UPDATE/INSERT/DELETE"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params or ())
                    connection.commit()
            return True
        except Exception as e:
            if connection.open:
                connection.rollback()
            st.error(f"Erro ao executar update: {e}")
            return False
    
    def test_connection(self):
        """Testa a conexão com o banco"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        result = cursor.fetchone()
                return result is not None
            except Exception as e:
                st.error(f"Erro ao testar conexão: {e}")
                return False
        return False
    
    def get_tables(self):
        """Lista todas as tabelas do banco"""
        query = "SHOW TABLES"
        return self.execute_query(query)
    
    def get_table_info(self, table_name):
        """Retorna informações sobre uma tabela"""
        query = f"DESCRIBE {table_name}"
        return self.execute_query(query)
    
    def close(self):
        """Fecha a conexão"""
        if self.engine:
            self.engine.dispose()
