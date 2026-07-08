"""
Módulo de conexão com MySQL.

Camada fina de acesso ao banco. Oferece dois caminhos:
- ``get_connection`` -> conexão PyMySQL nova a cada chamada (de propósito NÃO
  cacheada; ver docstring do método) para SELECT/UPDATE avulsos.
- ``get_engine`` -> engine SQLAlchemy cacheado (``st.cache_resource``), usado
  para leituras com pandas (``read_sql``) e reaproveitamento de pool.

As credenciais vêm do .env (MYSQL_HOST/PORT/DB/USER/PASSWORD), carregado no
import via ``load_dotenv()``.
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
        """Lê as credenciais do .env. O engine SQLAlchemy só é criado sob demanda."""
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
        """Retorna um engine SQLAlchemy (cacheado entre reruns do Streamlit).

        O parâmetro é ``_self`` (com underscore) porque ``st.cache_resource``
        tenta hashear os argumentos; o underscore instrui o Streamlit a ignorar
        ``self`` no hash. ``pool_pre_ping`` testa a conexão antes de usá-la e
        ``pool_recycle=1800`` recicla conexões ociosas há 30 min, evitando o
        erro de sessão MySQL expirada.
        """
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
        """Executa um SELECT e devolve todas as linhas como lista de dicts.

        Retorna None se a conexão falhar ou a query der erro (o erro aparece na
        UI via ``st.error``). ``params`` é passado ao driver para binding seguro
        dos valores (evita SQL injection). O ``with connection`` fecha o socket
        ao fim — coerente com a política de não cachear conexões.
        """
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
        """Executa INSERT/UPDATE/DELETE com commit. True em sucesso, False em erro.

        Em caso de exceção faz rollback (se a conexão ainda estiver aberta) para
        não deixar a transação pela metade.
        """
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
        """Testa a conexão executando um ``SELECT 1``. True se o banco respondeu."""
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
        """Retorna o schema (DESCRIBE) de uma tabela.

        ``table_name`` é interpolado direto na query porque identificadores
        (nomes de tabela) não podem ir como parâmetro do driver; use apenas com
        nomes vindos de fonte confiável.
        """
        query = f"DESCRIBE {table_name}"
        return self.execute_query(query)
    
    def close(self):
        """Descarta o pool do engine SQLAlchemy (libera as conexões abertas)."""
        if self.engine:
            self.engine.dispose()
