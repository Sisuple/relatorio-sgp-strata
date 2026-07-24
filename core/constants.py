"""Constantes de apresentação do relatório (títulos e menu).

Reúne os textos fixos usados pela UI: o título da marca exibido na sidebar e
a definição declarativa dos itens do menu lateral. Ponto único de edição desses
rótulos — quem os consome (ex.: components/layout/sidebar.py) apenas lê daqui.
"""

# Título da marca, exibido no topo da sidebar (ver render_sidebar).
PAGE_TITLE = "SIGMA"
# Rodovia pré-selecionada por padrão quando o banco ainda não retornou opções.
DEFAULT_ROAD = ""

# Não usar rodovias fictícias como fallback. Se o banco não trouxer rodovia,
# a tela deve avisar ausência de dados em vez de parecer que há dado real.
AVAILABLE_ROADS: list[str] = []

# Definição declarativa do menu lateral. Cada item vira um link ?page=<key>
# (ver sidebar.py). Campos: key (rota/?page), label (rótulo), description (subtítulo),
# icon (chave do SVG em _ICON_SVGS na sidebar) e group (rótulo da seção acima do item;
# None = sem cabeçalho de seção, fica "solto" no menu). A ORDEM aqui é a ordem exibida;
# itens do mesmo group consecutivos ficam agrupados sob um único cabeçalho.
MENU_ITEMS = [
    {
        "key": "visaogeral",
        "label": "Visão geral",
        "description": "Panorama executivo da rede",
        "icon": "grid",
        "group": "Análise Gerencial",
    },
    {
        "key": "overview",
        "label": "Diagnóstico",
        "description": "Como está minha rede agora?",
        "icon": "search",
        "group": "Análise Gerencial",
    },
    {
        "key": "solucoes",
        "label": "Soluções",
        "description": "O que fazer e onde?",
        "icon": "tool",
        "group": "Análise Gerencial",
    },
    {
        "key": "comparativo",
        "label": "Comparativo entre cenários",
        "description": "Compare recortes e metodologias",
        "icon": "compare",
        "group": "Análise Gerencial",
    },
    {
        "key": "cenario",
        "label": "Cenário econômico",
        "description": "Quanto custa e o que evita?",
        "icon": "dollar",
        "group": "Análise Gerencial",
    },
    {
        "key": "trafego",
        "label": "Tráfego",
        "description": "Volume e composição por trecho",
        "icon": "truck",
        "group": "Análise Técnica",
    },
    {
        "key": "pavimentacao",
        "label": "Pavimentação",
        "description": "Estrutura e condição do pavimento",
        "icon": "road",
        "group": "Análise Técnica",
    },
    {
        "key": "geotecnia",
        "label": "Geotecnia",
        "description": "Estrutura por camadas",
        "icon": "layers",
        "group": "Análise Técnica",
    },
    # {
    #     "key": "risco",
    #     "label": "IAGON",
    #     "description": "Pergunte, analise e exporte",
    #     "icon": "spark",
    # },
]
