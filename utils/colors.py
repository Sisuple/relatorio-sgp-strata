"""Paleta base da UI (cores de fundo, superfície, texto e acentos).

Tokens de cor hex reutilizados por toda a interface. É a paleta "de chrome"
(estrutura visual escura do app) — distinta das paletas semânticas de condição
(IAP/ICDS/solução), que ficam hardcoded nos componentes de gráfico/mapa.
Ver README.md Parte II §11.4 sobre as cores hardcoded do projeto.
"""

# Fundos e superfícies do tema escuro (do mais escuro ao mais claro) + borda.
BACKGROUND = "#061018"
SURFACE = "#0b1d28"
SURFACE_ALT = "#0d2633"
BORDER = "#1c3442"
# Texto principal (claro) e texto secundário/esmaecido.
TEXT_PRIMARY = "#f4f7fb"
TEXT_MUTED = "#92a1ad"
# Cores de acento para destaques, tons e status na UI.
CYAN = "#00c2e8"
GREEN = "#22c55e"
RED = "#ff314a"
ORANGE = "#ff8a00"
YELLOW = "#facc15"
BLUE = "#1fa2ff"
