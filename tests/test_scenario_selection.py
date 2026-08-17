"""Seleção de múltiplos cenários no mesmo sentido e aviso de dupla contagem.

Até 08/2026 o filtro impedia dois `Crescente` (ou dois `Decrescente`) juntos. A
regra valia enquanto um sentido era sempre uma análise só, mas passou a barrar o
caso real de um mesmo sentido dividido em trechos analisados com parâmetros
diferentes. Agora só `Todos` é exclusivo, e a dupla contagem por km sobreposto é
avisada em vez de bloqueada. Estes testes fixam esse contrato.
"""

from services.overview_service import km_ranges_overlap


def _options():
    return [
        {"token": "088::i", "road_code": "088", "pista": "crescente",
         "scenario_key": "377:1", "display_label": "I_SP088_2026 - CRESCENTE"},
        {"token": "088::ii", "road_code": "088", "pista": "crescente",
         "scenario_key": "386:1", "display_label": "II_SP088_2026 - CRESCENTE"},
        {"token": "088::de", "road_code": "088", "pista": "decrescente",
         "scenario_key": "385:1", "display_label": "I_SP088_2026 - DECRESCENTE"},
        {"token": "088::todos", "road_code": "088", "pista": "todos",
         "scenario_key": "999:1", "display_label": "TODOS"},
        {"token": "055::cr", "road_code": "055", "pista": "crescente",
         "scenario_key": "394:1", "display_label": "IV_SP055_2026 - CRESCENTE"},
    ]


def _sanitize(selected, previous=None):
    import app

    return app._sanitize_network_scenario_selection(
        selected, _options(), previous_tokens=previous or []
    )


def test_dois_crescentes_sao_permitidos():
    """O caso que motivou a mudança: mesmo sentido, trechos diferentes."""
    kept, message = _sanitize(["088::i", "088::ii"])

    assert kept == ["088::i", "088::ii"]
    assert message is None


def test_tres_cenarios_do_mesmo_sentido_sao_permitidos():
    kept, _ = _sanitize(["088::i", "088::ii", "055::cr"])

    assert kept == ["088::i", "088::ii", "055::cr"]


def test_crescente_com_decrescente_continua_permitido():
    kept, message = _sanitize(["088::i", "088::de"])

    assert kept == ["088::i", "088::de"]
    assert message is None


def test_todos_continua_exclusivo_e_cede_ao_clique_novo():
    """`Todos` já é a rodovia inteira: somar outro cenário conta km duas vezes."""
    kept, message = _sanitize(["088::todos", "088::i"], previous=["088::todos"])

    assert kept == ["088::i"]
    assert message is not None


def test_todos_recem_clicado_descarta_os_demais():
    kept, _ = _sanitize(["088::i", "088::todos"], previous=["088::i"])

    assert kept == ["088::todos"]


def test_exclusividade_de_todos_e_por_rodovia():
    """`Todos` da 088 não interfere no cenário da 055."""
    kept, _ = _sanitize(["088::todos", "055::cr"])

    assert kept == ["088::todos", "055::cr"]


def test_km_sobreposto_e_detectado():
    assert km_ranges_overlap([(40.5, 49.4)], [(40.5, 49.4)]) == (40.5, 49.4)
    assert km_ranges_overlap([(40.5, 49.4)], [(41.9, 42.8)]) == (41.9, 42.8)


def test_trechos_disjuntos_nao_sao_sobreposicao():
    assert km_ranges_overlap([(32.0, 39.2)], [(40.5, 49.4)]) is None


def test_trechos_que_apenas_se_encostam_nao_sao_sobreposicao():
    """Uma análise termina no km em que a outra começa — encosto, não superposição."""
    assert km_ranges_overlap([(32.0, 39.2)], [(39.2, 45.0)]) is None


# ---------------------------------------------------------------------------
# Offset do mapa: só desempilha geometria que coincide.
# ---------------------------------------------------------------------------

# km_inicial/km_final por análise, no lugar do banco.
_FOOTPRINTS = {
    377: [(32.0, 39.2)],    # I_SP088_2026 CRESCENTE
    378: [(32.0, 39.2)],    # I_SP088_2026 DECRESCENTE (mesmo km, outro sentido)
    386: [(40.5, 49.4)],    # II_SP088_2026 CRESCENTE — continuação de 377
    388: [(40.5, 49.4)],    # II_SP088_2026 CRESCENTE Sem Reforço — mesmo km de 386
    389: [(40.5, 49.4)],    # II_SP088_2026 DECRESCENTE
}
_PISTAS = {377: "CRESCENTE", 378: "DECRESCENTE", 386: "CRESCENTE",
           388: "CRESCENTE", 389: "DECRESCENTE"}


def _offsets(analises):
    """`_scenario_map_offsets` com os footprints acima em vez do banco."""
    import app

    keys = [f"{a}:1" for a in analises]
    by_key = {f"{a}:1": {"key": f"{a}:1", "pista": _PISTAS[a], "cenario": ""} for a in analises}
    original = app.get_scenario_km_ranges
    app.get_scenario_km_ranges = lambda ids: {i: _FOOTPRINTS[i] for i in ids if i in _FOOTPRINTS}
    try:
        return app._scenario_map_offsets(keys, by_key)
    finally:
        app.get_scenario_km_ranges = original


def test_cenario_unico_fica_no_eixo_real():
    assert _offsets([377]) == [0.0]


def test_sentidos_opostos_no_mesmo_km_vao_para_lados_opostos():
    """Comportamento histórico preservado: é o caso comum Crescente × Decrescente."""
    assert _offsets([377, 378]) == [0.5, -0.5]


def test_trechos_em_continuacao_nao_recebem_offset():
    """km disjuntos = mesma rodovia seguindo em frente; nada a desempilhar, então
    os dois ficam no eixo real em vez de saírem da posição verdadeira."""
    assert _offsets([377, 386]) == [0.0, 0.0]


def test_mesmo_sentido_no_mesmo_km_abre_em_leque():
    """Sem o leque a última camada desenhada cobre a anterior e um trecho
    desaparece do mapa."""
    assert _offsets([386, 388]) == [1 / 3, 2 / 3]


def test_continuacao_nao_entra_no_leque_dos_coincidentes():
    assert _offsets([386, 388, 377]) == [1 / 3, 2 / 3, 0.0]


def test_grupos_de_sobreposicao_independentes_usam_o_lado_inteiro():
    """Dois pares CR+DE em trechos diferentes são 2 grupos: cada um usa ±0,5, senão
    a linha do Crescente daria um degrau na virada de um trecho para o outro."""
    assert _offsets([377, 378, 386, 389]) == [0.5, -0.5, 0.5, -0.5]


# ---------------------------------------------------------------------------
# Telas multi-rodovia: cada rodovia resolve o seu offset por conta
# ---------------------------------------------------------------------------

def _offsets_multi(pares):
    """`_road_scenario_map_offsets` com os footprints do teste em vez do banco."""
    import app

    original_km = app.get_scenario_km_ranges
    original_cen = app.get_available_scenarios
    app.get_scenario_km_ranges = lambda ids: {i: _FOOTPRINTS[i] for i in ids if i in _FOOTPRINTS}
    app.get_available_scenarios = lambda road, matrix_type: [
        {"key": f"{a}:1", "pista": _PISTAS[a], "cenario": ""} for a in _PISTAS
    ]
    try:
        return app._road_scenario_map_offsets(
            [(road, f"{a}:1") for road, a in pares], "Paragon"
        )
    finally:
        app.get_scenario_km_ranges = original_km
        app.get_available_scenarios = original_cen


def test_multi_rodovia_resolve_cada_rodovia_por_conta():
    """Um cenário da BR-055 não disputa eixo com um da BR-088: cada par CR+DE da sua
    rodovia usa o lado inteiro, em vez de os quatro se espalharem por índice."""
    assert _offsets_multi([
        ("BR-055", 377), ("BR-055", 378),
        ("BR-088", 377), ("BR-088", 378),
    ]) == [0.5, -0.5, 0.5, -0.5]


def test_multi_rodovia_com_um_cenario_por_rodovia_nao_desloca():
    """Sozinho na sua rodovia, o cenário fica no eixo real."""
    assert _offsets_multi([("BR-055", 377), ("BR-088", 386)]) == [0.0, 0.0]


def test_multi_rodovia_mantem_mesmo_sentido_do_mesmo_lado():
    """Dois Crescentes coincidentes na mesma rodovia abrem em leque do MESMO lado."""
    assert _offsets_multi([("BR-055", 386), ("BR-055", 388)]) == [1 / 3, 2 / 3]


def test_lacuna_preenchida_por_sub_trecho_nao_avisa():
    """Caso real da BR-055 DECRESCENTE: a análise principal abre uma lacuna em
    368,2–369,4 e um cenário dedicado cobre exatamente esse vão."""
    principal = [(359.2, 368.2), (369.4, 380.2)]
    sub_trecho = [(368.2, 369.4)]

    assert km_ranges_overlap(principal, sub_trecho) is None
