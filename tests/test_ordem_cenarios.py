"""Todas as telas listam os cenários na MESMA ordem.

A ordem canônica é a que `get_available_scenarios` devolve — Segmento Homogêneo
primeiro, depois 1km, depois o resto, e dentro de cada grupo os mais recentes antes
(`ORDER BY ordem_cenario, updated_at DESC, agc.id DESC`). Diagnóstico, Soluções,
Comparativo e os filtros mestres do econômico já a usavam.

A Visão geral e o Cenário econômico eram a exceção: `_collect_network_scenario_options`
reordenava alfabeticamente pelo rótulo. Como toda tela pré-seleciona o PRIMEIRO item
da sua lista, a Visão geral abria em "Duplicação…" (D no alfabeto) e o Diagnóstico no
SH — mesma rodovia, mesmos cenários, cenário inicial diferente, dando a impressão de
que as listas eram diferentes.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_a_visao_geral_nao_reordena_os_cenarios():
    """Sem o `sort` alfabético, o loop preserva a ordem do banco por rodovia."""
    app = (RAIZ / "app.py").read_text(encoding="utf-8")

    assert 'options.sort(key=lambda item: (str(item["road"]), str(item["display_label"])))' not in app


def test_a_ordem_do_banco_prioriza_segmento_homogeneo():
    """É a ordem que todas as telas herdam; se o CASE sair da query, a unificação
    perde o critério e volta a valer a ordem física das linhas."""
    servico = (RAIZ / "services" / "overview_service.py").read_text(encoding="utf-8")

    assert "ORDER BY ordem_cenario, agdt.updated_at DESC, agc.id DESC" in servico
    assert "WHEN LOWER(agdt.nome) LIKE '%%(sh)%%' THEN 1" in servico
    assert "WHEN LOWER(agdt.nome) LIKE '%%(1km)%%' THEN 2" in servico


def test_nenhuma_tela_reordena_a_lista_de_cenarios():
    """As telas montam a lista por list comprehension sobre `scenarios`, o que
    preserva a ordem. Um `sorted(...)` sobre as chaves reintroduziria o problema."""
    app = (RAIZ / "app.py").read_text(encoding="utf-8")

    suspeitos = [
        'sorted(s["key"] for s in scenarios)',
        "sorted(scenario_keys)",
        "sorted(available_scenario_keys)",
        'scenario_keys.sort()',
    ]
    for trecho in suspeitos:
        assert trecho not in app, trecho
