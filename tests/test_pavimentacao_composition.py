"""Composições IRI / ATR / IGG sobre a MESMA base de km.

Os 3 donuts da tela de Pavimentação fechavam em km diferentes (na BR-055: IRI
931,7 · ATR 1.014,8 · IGG 356,9 — num trecho de 134 km por sentido/faixa). Quatro
causas somadas, todas corrigidas em 08/2026:

1. as views guardam VÁRIOS levantamentos do mesmo trecho (2025, 2026, mais os
   ciclos de "Implantação" de 2027–2032, que são trecho projetado) e a soma linha
   a linha contava o mesmo km em cada um;
2. o IGG calculava a extensão agrupando só por sentido, sem a faixa — com 3
   faixas no mesmo km, a maioria das leituras ficava com extensão zero;
3. o IRI usava a coluna `extensao` da view, que se sobrepõe entre leituras;
4. no sentido decrescente a view grava `km_final < km_inicial`, e toda subtração
   dava negativo.

A base agora é a união do km medido pelos três, e o que falta em um deles entra
como "Sem dado" — então o total é idêntico nos três, por construção.
"""

import pandas as pd

from services.pavimentacao_service import (
    MAX_READING_GAP_KM,
    NO_DATA_CLASS,
    _claimed_by_class,
    _merge_intervals,
    _subtract_intervals,
    _total_km,
)


# ---------------------------------------------------------------------------
# Aritmética de intervalos — a base de tudo
# ---------------------------------------------------------------------------

def test_uniao_junta_sobreposicao():
    assert _merge_intervals([(0, 10), (5, 15)]) == [(0, 15)]


def test_uniao_preserva_trechos_separados():
    assert _merge_intervals([(0, 10), (20, 30)]) == [(0, 10), (20, 30)]


def test_uniao_descarta_intervalo_degenerado():
    """Leitura sem extensão (km_final == km_inicial) não é km de pista."""
    assert _merge_intervals([(5, 5), (0, 10)]) == [(0, 10)]


def test_uniao_de_dois_levantamentos_do_mesmo_trecho_nao_dobra_o_km():
    """O caso que inflava o total: 2025 e 2026 medindo o mesmo km."""
    km = _total_km(_merge_intervals([(211.4, 247.7), (211.5, 247.7)]))
    assert abs(km - 36.3) < 1e-9


def test_subtracao_abre_buraco_no_meio():
    assert _subtract_intervals([(0, 10)], [(4, 6)]) == [(0, 4), (6, 10)]


def test_subtracao_sem_interseccao_nao_altera():
    assert _subtract_intervals([(0, 10)], [(20, 30)]) == [(0, 10)]


def test_subtracao_total_zera():
    assert _subtract_intervals([(0, 10)], [(0, 10)]) == []


# ---------------------------------------------------------------------------
# "Mais recente por km"
# ---------------------------------------------------------------------------

def _leituras(linhas):
    return pd.DataFrame(linhas, columns=["km_lo", "km_hi", "sentido", "faixa", "ano", "classe"])


def test_levantamento_mais_novo_vence_no_km_sobreposto():
    """2025 e 2026 medem o mesmo km com classes diferentes: vale 2026, e o km
    aparece UMA vez."""
    df = _leituras([
        (0.0, 10.0, "crescente", "1", 2025, "Ruim"),
        (0.0, 10.0, "crescente", "1", 2026, "Bom"),
    ])
    por_classe = _claimed_by_class(df, ano=None)

    assert _total_km(por_classe.get("Bom", [])) == 10.0
    assert "Ruim" not in por_classe


def test_km_que_so_o_levantamento_antigo_cobre_e_preservado():
    """Caso real da BR-088 decrescente faixa 3: 0,43 km medidos só em 2025."""
    df = _leituras([
        (0.0, 10.0, "crescente", "1", 2025, "Ruim"),
        (0.0, 8.0, "crescente", "1", 2026, "Bom"),
    ])
    por_classe = _claimed_by_class(df, ano=None)

    assert _total_km(por_classe["Bom"]) == 8.0
    assert _total_km(por_classe["Ruim"]) == 2.0


def test_ano_explicito_ignora_os_demais():
    df = _leituras([
        (0.0, 10.0, "crescente", "1", 2025, "Ruim"),
        (0.0, 10.0, "crescente", "1", 2026, "Bom"),
    ])
    por_classe = _claimed_by_class(df, ano=2025)

    assert _total_km(por_classe["Ruim"]) == 10.0
    assert "Bom" not in por_classe


def test_no_mesmo_ano_a_pior_classe_vence_a_sobreposicao():
    """Duas leituras do mesmo levantamento no mesmo km: critério conservador."""
    df = _leituras([
        (0.0, 10.0, "crescente", "1", 2026, "Bom"),
        (0.0, 10.0, "crescente", "1", 2026, "Ruim"),
    ])
    por_classe = _claimed_by_class(df, ano=None)

    assert _total_km(por_classe["Ruim"]) == 10.0
    assert "Bom" not in por_classe


def test_classes_nunca_se_sobrepoem():
    """Cada km pertence a uma classe só — é o que garante que a soma das classes
    não passe da base."""
    df = _leituras([
        (0.0, 10.0, "crescente", "1", 2026, "Bom"),
        (5.0, 15.0, "crescente", "1", 2026, "Regular"),
        (12.0, 20.0, "crescente", "1", 2026, "Ruim"),
    ])
    por_classe = _claimed_by_class(df, ano=None)
    soma = sum(_total_km(ivs) for ivs in por_classe.values())
    uniao = _total_km(_merge_intervals([iv for ivs in por_classe.values() for iv in ivs]))

    assert soma == uniao == 20.0


def test_sem_leitura_nao_reivindica_km():
    assert _claimed_by_class(_leituras([]), ano=None) == {}


# ---------------------------------------------------------------------------
# Contrato do módulo
# ---------------------------------------------------------------------------

def test_teto_de_lacuna_existe_e_e_pequeno():
    """Sem teto, o vão de 44,5 km entre os trechos IV e V da BR-055 entrava como
    pavimento medido e inflava FWD/IGG em 33%."""
    assert 0 < MAX_READING_GAP_KM <= 0.1


def test_classe_de_km_sem_dado():
    assert NO_DATA_CLASS == "Sem dado"
