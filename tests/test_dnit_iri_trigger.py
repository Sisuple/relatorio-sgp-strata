"""Cor por IRI × gatilho na Visão geral e no Diagnóstico (Matriz Cadastrada).

Régua definida pelo cliente em 08/2026:

    verde    IRI < 0,95 × gatilho
    amarelo  0,95 × gatilho <= IRI <= gatilho
    vermelho IRI > gatilho

E o gatilho vem da faixa de IDADE do pavimento:

    1º ao 3º ano      3,46
    4º ao 13º ano     2,69
    14º ao 28º ano    2,46
    a partir do 29º   2,46

Os gatilhos são fixos no código de propósito, não lidos da matriz. Oito matrizes
do SGP (REF 4, REF 12, FR17, FR11, RL+FRR…) gravam `IRI > 1`, que não é gatilho
técnico — é um "sempre verdadeiro" para a solução sair. Como o menor IRI da base é
1,13, usar aquele 1,0 pintaria a rede inteira de vermelho.
"""

from services.overview_service import (
    DNIT_IRI_BAND_ABOVE,
    DNIT_IRI_BAND_BELOW,
    DNIT_IRI_BAND_COLORS,
    DNIT_IRI_BAND_LEGEND,
    DNIT_IRI_BAND_LIMIT,
    DNIT_IRI_BAND_ORDER,
    DNIT_IRI_TRIGGERS,
    _dnit_age_from_matrix_name,
    dnit_iri_band,
    dnit_iri_trigger_for_age,
)

VERDE, AMARELO, VERMELHO = "#00a651", "#fff200", "#d71920"


# ---------------------------------------------------------------------------
# Gatilho por idade
# ---------------------------------------------------------------------------

def test_gatilho_por_faixa_de_idade():
    assert dnit_iri_trigger_for_age(1) == 3.46
    assert dnit_iri_trigger_for_age(3) == 3.46
    assert dnit_iri_trigger_for_age(4) == 2.69
    assert dnit_iri_trigger_for_age(13) == 2.69
    assert dnit_iri_trigger_for_age(14) == 2.46
    assert dnit_iri_trigger_for_age(28) == 2.46
    assert dnit_iri_trigger_for_age(29) == 2.46
    assert dnit_iri_trigger_for_age(60) == 2.46


def test_idade_desconhecida_usa_a_primeira_faixa():
    assert dnit_iri_trigger_for_age(None) == 3.46
    assert dnit_iri_trigger_for_age(0) == 3.46


def test_as_faixas_nao_tem_buraco_nem_sobreposicao():
    for (_, fim_a, _), (inicio_b, _, _) in zip(DNIT_IRI_TRIGGERS, DNIT_IRI_TRIGGERS[1:]):
        assert fim_a is not None and inicio_b == fim_a + 1


# ---------------------------------------------------------------------------
# Idade lida do nome da matriz
# ---------------------------------------------------------------------------

def test_idade_do_nome_da_matriz():
    assert _dnit_age_from_matrix_name("1º ao 3º ano - Micro (1,5)+RL+FRR(4)") == 1
    assert _dnit_age_from_matrix_name("4º ao 13º ano - Micro (1,5)+RL+FRR(4)") == 4
    assert _dnit_age_from_matrix_name("14º ao 28º ano - Micro (1,5)+RL+FRR(4)") == 14
    assert _dnit_age_from_matrix_name("a partir do 29º ano - Micro (1,5)+RL+FRR(4)") == 29


def test_matriz_3_ao_4_ano_cai_na_primeira_faixa():
    """Confirmado com o cliente: o ciclo 2027–2028 é 1º ao 3º ano, gatilho 3,46.
    Vale o INÍCIO da faixa da matriz (3º ano), que está dentro de 1–3."""
    idade = _dnit_age_from_matrix_name("3º ao 4º ano - Reforço e Reconstrução - IRI 2,1")
    assert idade == 3
    assert dnit_iri_trigger_for_age(idade) == 3.46


def test_matriz_de_solucao_forcada_nao_declara_idade():
    """Sem idade no nome, o gatilho sai da ordem do ciclo — não do `IRI > 1` gravado."""
    for nome in ("Matriz REF 12", "Matriz REF 4", "Matriz FR17 + CBUQ(17)",
                 "Matriz FR11 + CBUQ(11) + CBUQ(4)", "RL+FRR(4)"):
        assert _dnit_age_from_matrix_name(nome) is None, nome


# ---------------------------------------------------------------------------
# Bandas de cor
# ---------------------------------------------------------------------------

def test_bandas_com_gatilho_269():
    # 0,95 x 2,69 = 2,5555
    assert dnit_iri_band(2.06, 2.69) == (DNIT_IRI_BAND_BELOW, VERDE)
    assert dnit_iri_band(2.55, 2.69) == (DNIT_IRI_BAND_BELOW, VERDE)
    assert dnit_iri_band(2.60, 2.69) == (DNIT_IRI_BAND_LIMIT, AMARELO)
    assert dnit_iri_band(2.69, 2.69) == (DNIT_IRI_BAND_LIMIT, AMARELO)
    assert dnit_iri_band(2.70, 2.69) == (DNIT_IRI_BAND_ABOVE, VERMELHO)


def test_bandas_com_gatilho_346():
    # 0,95 x 3,46 = 3,287
    assert dnit_iri_band(2.03, 3.46) == (DNIT_IRI_BAND_BELOW, VERDE)
    assert dnit_iri_band(3.30, 3.46) == (DNIT_IRI_BAND_LIMIT, AMARELO)
    assert dnit_iri_band(3.50, 3.46) == (DNIT_IRI_BAND_ABOVE, VERMELHO)


def test_o_gatilho_exato_e_amarelo_nao_vermelho():
    """A régua é IRI <= gatilho para amarelo; vermelho é estritamente acima."""
    for gatilho in (3.46, 2.69, 2.46):
        assert dnit_iri_band(gatilho, gatilho)[0] == DNIT_IRI_BAND_LIMIT


def test_iri_baixo_nunca_fica_vermelho():
    """O menor IRI da base é 1,13. Com os gatilhos por idade ele é sempre verde —
    era exatamente isso que o `IRI > 1` das matrizes de solução forçada quebrava."""
    for gatilho in (3.46, 2.69, 2.46):
        assert dnit_iri_band(1.13, gatilho) == (DNIT_IRI_BAND_BELOW, VERDE)


def test_paleta_das_bandas():
    assert DNIT_IRI_BAND_COLORS[DNIT_IRI_BAND_BELOW] == VERDE
    assert DNIT_IRI_BAND_COLORS[DNIT_IRI_BAND_LIMIT] == AMARELO
    assert DNIT_IRI_BAND_COLORS[DNIT_IRI_BAND_ABOVE] == VERMELHO


def test_as_bandas_sao_bom_regular_ruim():
    """Decisão do cliente (08/2026): um vocabulário só para TODOS os gráficos de
    IRI — mapa, donut, filtro, card e diagrama linear —, igual ao que a tela de
    Pavimentação já usa."""
    assert DNIT_IRI_BAND_BELOW == "Bom"
    assert DNIT_IRI_BAND_LIMIT == "Regular"
    assert DNIT_IRI_BAND_ABOVE == "Ruim"


def test_legenda_ordenada_do_pior_para_o_melhor():
    assert DNIT_IRI_BAND_ORDER == ["Ruim", "Regular", "Bom"]


def test_legenda_do_mapa_traz_o_nome_e_a_regra():
    """No mapa o nome da classe sozinho não diz onde está o corte; a regra vai ao
    lado. Sem o VALOR do gatilho, que varia com a idade e com o ano — esse aparece
    no tooltip de cada trecho."""
    assert DNIT_IRI_BAND_LEGEND[DNIT_IRI_BAND_ABOVE] == "Ruim · IRI > Gatilho"
    assert DNIT_IRI_BAND_LEGEND[DNIT_IRI_BAND_LIMIT] == "Regular · IRI ≥ 0,95 × Gatilho"
    assert DNIT_IRI_BAND_LEGEND[DNIT_IRI_BAND_BELOW] == "Bom · IRI < 0,95 × Gatilho"

    for banda, rotulo in DNIT_IRI_BAND_LEGEND.items():
        assert rotulo.startswith(banda), banda
        # A legenda tem 280px: rótulo longo quebra em duas linhas.
        assert len(rotulo) <= 32, rotulo


def test_as_bandas_de_iri_nao_colidem_com_as_familias_de_solucao():
    """Bom/Regular/Ruim (condição do IRI) e as famílias de solução são coisas
    distintas e aparecem em telas diferentes; só as cores é que se repetem."""
    from services.overview_service import DNIT_FAMILY_ORDER

    assert not set(DNIT_IRI_BAND_ORDER) & set(DNIT_FAMILY_ORDER)
