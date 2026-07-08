"""Constantes de apresentação do relatório (títulos, rodovias-fallback e menu).

Reúne os textos fixos usados pela UI: o título/subtítulo da marca exibidos na
sidebar, a lista de rodovias-fallback oferecida quando não há seleção real e a
definição declarativa dos itens do menu lateral. Ponto único de edição desses
rótulos — quem os consome (ex.: components/layout/sidebar.py) apenas lê daqui.
"""

# Título e subtítulo da marca, exibidos no topo da sidebar (ver render_sidebar).
PAGE_TITLE = "IAGON"
PAGE_SUBTITLE = "Metodologia Paragon"
# Rodovia pré-selecionada por padrão e também primeiro item da lista abaixo.
DEFAULT_ROAD = "BR-101 — Trecho RJ (Niterói → Campos)"

# Rodovias-fallback oferecidas na UI quando não há uma seleção real vinda do banco.
AVAILABLE_ROADS = [
    DEFAULT_ROAD,
    "BR-116 — Trecho RJ (Além Paraíba → Rio)",
    "BR-040 — Trecho RJ (Petrópolis → Juiz de Fora)",
]

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
        "key": "cenario",
        "label": "Cenário econômico",
        "description": "Quanto custa e o que evita?",
        "icon": "scale",
    },
    {
        "key": "projecao",
        "label": "Projeção",
        "description": "Como evoluirá no tempo?",
        "icon": "trend",
    },
    {
        "key": "risco",
        "label": "IAGON",
        "description": "Pergunte, analise e exporte",
        "icon": "spark",
    },
]
