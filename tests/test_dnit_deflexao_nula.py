"""Ano sem Dadm não pode derrubar a Visão geral / Diagnóstico.

`_get_dnit_overview_from_database` calcula o % de km com deficiência estrutural
comparando Dc com Dadm. As duas grandezas vêm de tabelas com escopo diferente:

- **Dc** de `analise_gerencial_parametros_iniciais`, por CICLO;
- **Dadm** de `analise_gerencial_desempenho_pavimento`, por ciclo **e ANO**.

Existe ano com Dc medido e nenhum Dadm (ex.: 2026 na BR-055). Nesse recorte a
coluna `dc` sai `float64` e a `dadm`, só com `None`, sai dtype `object` — e

    segments["dc"].notna() & segments["dadm"].notna() & (segments["dc"] > segments["dadm"])

levanta `TypeError: '>' not supported between instances of 'float' and 'NoneType'`.
O `notna()` antes não protege: o `&` do pandas não faz curto-circuito, a comparação
é avaliada na Series inteira de qualquer forma.

O erro era intermitente e virou constante quando o filtro de ano deixou de listar
só anos com intervenção e passou a oferecer todos os anos com IRI/IGG.
"""

import pandas as pd


def _mascara_deficiencia(segments: pd.DataFrame) -> pd.Series:
    """Réplica do trecho corrigido em `_get_dnit_overview_from_database`."""
    dc = pd.to_numeric(segments["dc"], errors="coerce")
    dadm = pd.to_numeric(segments["dadm"], errors="coerce")
    return dc.notna() & dadm.notna() & (dc > dadm)


def _mascara_antiga(segments: pd.DataFrame) -> pd.Series:
    """Como era antes — mantida para o teste provar que o cenário quebrava."""
    return (
        segments["dc"].notna()
        & segments["dadm"].notna()
        & (segments["dc"] > segments["dadm"])
    )


def _ano_sem_dadm() -> pd.DataFrame:
    """O recorte que quebrava: Dc medido em todos, Dadm em nenhum.

    Confirmado contra o banco — BR-055, `V_SP055_2026 - DECRESCENTE`, ano 2026.
    `dc` sai float64 e `dadm` object, e é essa combinação que estoura.
    """
    df = pd.DataFrame([{"dc": 1.20, "dadm": None}, {"dc": 0.50, "dadm": None}])
    assert str(df["dc"].dtype) == "float64"
    assert str(df["dadm"].dtype) == "object"
    return df


def test_a_formula_antiga_quebrava_no_ano_sem_dadm():
    """Fixa a causa: sem isso os testes abaixo não provam nada."""
    try:
        _mascara_antiga(_ano_sem_dadm())
    except TypeError as erro:
        assert "not supported between instances of 'float' and 'NoneType'" in str(erro)
        return
    raise AssertionError("a fórmula antiga deveria levantar TypeError sem Dadm")


def test_ano_sem_dadm_nao_quebra_e_nao_conta_deficiencia():
    """Sem Dadm não há como afirmar deficiência estrutural: ninguém entra."""
    mascara = _mascara_deficiencia(_ano_sem_dadm())

    assert not mascara.any()
    assert mascara.dtype == bool


def test_com_dadm_a_deficiencia_e_apontada():
    """A correção não pode zerar o cálculo onde o dado existe."""
    segments = pd.DataFrame(
        [
            {"dc": 1.20, "dadm": 0.80},   # Dc > Dadm -> deficiente
            {"dc": 0.50, "dadm": 0.90},   # Dc <= Dadm -> ok
            {"dc": None, "dadm": None},   # sem medição
        ]
    )

    assert list(_mascara_deficiencia(segments)) == [True, False, False]


def test_recorte_inteiro_sem_deflexao():
    """Nem Dc nem Dadm: as duas colunas viram object e a máscara tem de sair vazia."""
    segments = pd.DataFrame([{"dc": None, "dadm": None} for _ in range(4)])

    mascara = _mascara_deficiencia(segments)

    assert not mascara.any()
    assert mascara.dtype == bool
