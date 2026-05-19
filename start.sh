#!/bin/bash

# Script para iniciar o Streamlit MySQL App

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Iniciando Streamlit MySQL App...${NC}"

# Diretório do projeto
PROJECT_DIR="/var/www/streamlit-app"
cd "$PROJECT_DIR" || exit 1

# Verifica se o arquivo .env existe
if [ ! -f .env ]; then
    echo -e "${YELLOW}Arquivo .env não encontrado!${NC}"
    echo "Copie o .env.example e configure suas credenciais:"
    echo "cp .env.example .env"
    exit 1
fi

# Ativa o ambiente virtual se existir
if [ -d "venv" ]; then
    echo "Ativando ambiente virtual..."
    source venv/bin/activate
else
    echo -e "${YELLOW}Ambiente virtual não encontrado. Execute:${NC}"
    echo "python3 -m venv venv"
    echo "source venv/bin/activate"
    echo "pip install -r requirements.txt"
fi

# Inicia o Streamlit
echo -e "${GREEN}Iniciando Streamlit na porta 8501...${NC}"
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
