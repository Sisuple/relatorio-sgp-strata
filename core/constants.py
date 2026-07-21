"""Constantes de apresentação do relatório (títulos e menu).

Reúne os textos fixos usados pela UI: o título/subtítulo da marca exibidos na
sidebar e a definição declarativa dos itens do menu lateral. Ponto único de edição desses
rótulos — quem os consome (ex.: components/layout/sidebar.py) apenas lê daqui.
"""

# Título e subtítulo da marca, exibidos no topo da sidebar (ver render_sidebar).
PAGE_TITLE = "IAGON"
PAGE_SUBTITLE = "Metodologia Paragon"
# Rodovia pré-selecionada por padrão quando o banco ainda não retornou opções.
DEFAULT_ROAD = ""

# Não usar rodovias fictícias como fallback. Se o banco não trouxer rodovia,
# a tela deve avisar ausência de dados em vez de parecer que há dado real.
AVAILABLE_ROADS: list[str] = []

# Definição declarativa do menu lateral. Cada item vira um link ?page=<key>
# (ver sidebar.py). Campos: key (rota/?page), label (rótulo), description (subtítulo)
# e icon (chave do SVG em _ICON_SVGS na sidebar). A ORDEM aqui é a ordem exibida.
MENU_ITEMS = [
    {
        "key": "visaogeral",
        "label": "Visão geral",
        "description": "Panorama executivo da rede",
        "icon": "grid",
    },
    {
        "key": "overview",
        "label": "Diagnóstico",
        "description": "Como está minha rede agora?",
        "icon": "activity",
    },
    {
        "key": "solucoes",
        "label": "Soluções",
        "description": "O que fazer e onde?",
        "icon": "tool",
    },
    {
        "key": "comparativo",
        "label": "Comparativo entre cenários",
        "description": "Compare recortes e metodologias",
        "icon": "compare",
    },
    {
        "key": "cenario",
        "label": "Cenário econômico",
        "description": "Quanto custa e o que evita?",
        "icon": "scale",
    },
    # {
    #     "key": "risco",
    #     "label": "IAGON",
    #     "description": "Pergunte, analise e exporte",
    #     "icon": "spark",
    # },
]
