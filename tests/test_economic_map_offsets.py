"""Afastamento lateral dos cenários no mapa, por rodovia.

`road_local_scenario_offsets` centralizava os cenários de cada rodovia por ÍNDICE.
Isso mandava dois cenários do MESMO sentido para lados opostos da pista, como se
fossem sentidos diferentes, e deslocava trechos em continuação (km disjuntos) que
não disputam eixo nenhum.

Quem decide o afastamento agora é `app._scenario_map_offsets` (e, nas telas
multi-rodovia, `app._road_scenario_map_offsets`), com a regra:

- só há deslocamento onde os cenários COINCIDEM em km;
- o lado vem do SENTIDO — um sentido fica todo do mesmo lado, Crescente e
  Decrescente ficam em lados opostos;
- vários cenários coincidentes do mesmo sentido abrem em leque dentro do seu lado.

Ver tests/test_scenario_selection.py para os testes dessa regra. Aqui ficam só as
garantias de que a função antiga não voltou a ser usada — ela é justamente o que
produzia o traçado costurando a rodovia.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_nenhum_mapa_usa_mais_o_leque_por_indice():
    """`i - (n - 1) / 2` espalhava os cenários por índice, ignorando o sentido."""
    app = (RAIZ / "app.py").read_text(encoding="utf-8")

    assert "i - (n - 1) / 2" not in app
    assert "idx - (len(road_scenarios) - 1) / 2" not in app


def test_app_nao_importa_mais_road_local_scenario_offsets():
    app = (RAIZ / "app.py").read_text(encoding="utf-8")

    assert "from utils.geo import road_local_scenario_offsets" not in app


def test_os_mapas_nao_reordenam_a_geometria_por_latitude():
    """`canonicalPath()` reordenava cada trecho comparando a LATITUDE do primeiro
    ponto com a do último. Numa rodovia leste-oeste o sinal virava ruído e trocava
    de segmento para segmento, invertendo o lado do offset: na BR-055, das 111
    emendas entre trechos, 109 vinham coerentes do banco e sobravam 81 invertidas.
    A ordem que chega do banco já é a de km crescente e tem de ser preservada."""
    for componente in ("components/maps/overview_map.py", "components/maps/dnit_map.py"):
        js = (RAIZ / componente).read_text(encoding="utf-8")
        # Procura a DECLARAÇÃO e a CHAMADA: o nome ainda aparece nos comentários que
        # registram por que a função saiu.
        assert "function canonicalPath" not in js, componente
        assert "canonicalPath(" not in js.replace("`canonicalPath()`", ""), componente


def test_o_offset_e_medido_em_metros_com_piso_em_pixels():
    """Em pixels puros a linha descolava do traçado: 18 px valem ~20 m no zoom
    fechado e centenas de metros no aberto. O piso cobre o oposto — precisa ser
    maior que a espessura da linha (5 px), senão os dois traços se sobrepõem."""
    for componente in ("components/maps/overview_map.py", "components/maps/dnit_map.py"):
        fonte = (RAIZ / componente).read_text(encoding="utf-8")
        assert "const GAP_M" in fonte, componente
        assert "function pixelsPerMeter" in fonte, componente
        # `const GAP_PX` era a régua antiga; `MIN_GAP_PX` (o piso) tem de continuar.
        assert "const GAP_PX" not in fonte, componente
        assert "const MIN_GAP_PX" in fonte, componente

        # o piso default tem de superar a espessura da linha
        for linha in fonte.splitlines():
            if linha.strip().startswith("min_gap_px:"):
                piso = float(linha.split("=")[1].strip().rstrip(","))
                assert piso > 5, f"{componente}: piso {piso} <= espessura da linha"
                break
        else:
            raise AssertionError(f"{componente}: min_gap_px não encontrado")
