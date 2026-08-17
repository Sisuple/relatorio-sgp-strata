"""Família de cor da solução na Matriz Cadastrada.

A cor do mapa e dos gráficos DNIT passou (08/2026) de faixa de IRI para
INTERVENÇÃO, usando a mesma leitura do Paragon:

    verde = conservação/superficial · amarelo = fresagem
    laranja = reforço              · vermelho = reconstrução

A classificação é por NOME do tipo de intervenção, não por `tipoId`:
`intervencao_tipos` é uma tabela por banco, então os ids não são estáveis entre
instalações — a terminologia DNIT é. Estes testes fixam a regra e cobrem os dois
vocabulários que o banco usa para a mesma coisa: o do catálogo
(`intervencao_tipos.nome`) e o comercial (`solucoes[].tipoNome`).
"""

from services.overview_service import (
    DNIT_FAMILY_COLORS,
    DNIT_FAMILY_NO_WORK,
    DNIT_FAMILY_ORDER,
    dnit_family_color,
    dnit_family_from_type_name,
    dnit_solution_family,
)

VERDE, AMARELO, LARANJA, VERMELHO = "#00a651", "#fff200", "#f2a51a", "#d71920"
AZUL = "#00c2e8"


# ---------------------------------------------------------------------------
# Nomes do catálogo (intervencao_tipos.nome)
# ---------------------------------------------------------------------------

def test_nomes_do_catalogo():
    assert dnit_family_from_type_name("Reconstrução") == "Reconstrução"
    assert dnit_family_from_type_name("Fresagem e recomposição") == "Fresagem e recomposição"
    assert dnit_family_from_type_name("Reforço CBUQ") == "Reforço"
    assert dnit_family_from_type_name("Microrrevestimento") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("Tapa-buraco") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("Remendo - trincas") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("Selagem de trincas") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("Reparo de bordo") == "Reparo localizado / Micro"


def test_tratamentos_superficiais_sao_conservacao():
    """TSD, TSS e fog sealing são funcionais, mesmo patamar do micro."""
    for nome in ("TSD + Microrrevestimento", "Tratamento superficial duplo",
                 "Tratamento superficial simples", "Fog sealing"):
        assert dnit_family_from_type_name(nome) == "Reparo localizado / Micro", nome


def test_reperfilamento_conta_como_fresagem():
    """Decisão do cliente em 08/2026: correção de perfil com material novo entra no
    amarelo, não no verde. Não existe nos dados atuais — vale para outras bases."""
    assert dnit_family_from_type_name("Reperfilamento") == "Fresagem e recomposição"


def test_drenagem_nao_define_cor():
    """Não é revestimento: entra na solução exibida, mas não colore o trecho."""
    assert dnit_family_from_type_name("Drenagem") is None


def test_tipo_desconhecido_vai_para_outras_solucoes():
    """Precisa aparecer como desconhecido na legenda em vez de ser pintado errado."""
    assert dnit_family_from_type_name("Serviço Que Nenhuma Base Tem") == "Outras soluções"


# ---------------------------------------------------------------------------
# Nomes comerciais gravados no JSON (solucoes[].tipoNome)
# ---------------------------------------------------------------------------

def test_nomes_comerciais_de_fresagem():
    """'FR4 + CBUQ(4)' é UM item: o CBUQ ali é a recomposição, não reforço."""
    for nome in ("FR4 + CBUQ(4)", "FR(11) + CBUQ (11)", "FR(17) + CBUQ (17)",
                 "FR5 + CBUQ(3) + CBUQ(4)"):
        assert dnit_family_from_type_name(nome) == "Fresagem e recomposição", nome


def test_cbuq_avulso_e_reforco_em_qualquer_espessura():
    for nome in ("CBUQ (4)", "CBUQ (5)", "CBUQ (8)"):
        assert dnit_family_from_type_name(nome) == "Reforço", nome


def test_rec_com_numero_e_reconstrucao():
    """'REC8' precisa virar Reconstrução sem que 'recomposição' também vire."""
    assert dnit_family_from_type_name("REC8") == "Reconstrução"
    assert dnit_family_from_type_name("REC4") == "Reconstrução"
    assert dnit_family_from_type_name("Fresagem e recomposição") == "Fresagem e recomposição"


def test_micro_rl_e_tsdp_comerciais():
    assert dnit_family_from_type_name("Micro(1,5)") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("Micro (0,8)") == "Reparo localizado / Micro"
    assert dnit_family_from_type_name("RL (Tapa-buraco)") == "Reparo localizado / Micro"
    # 'TSDp' é como o banco grava o tratamento superficial duplo.
    assert dnit_family_from_type_name("TSDp") == "Reparo localizado / Micro"


# ---------------------------------------------------------------------------
# Solução completa do segmento — a mais severa vence
# ---------------------------------------------------------------------------

def test_combinacoes_reais_do_banco():
    casos = [
        # (itens do segmento, família esperada)
        (["FR4 + CBUQ(4)", "Drenagem"], "Fresagem e recomposição"),
        (["RL (Remendo - trincas)", "RL (Tapa-buraco)",
          "RL (Remendo - desgaste)", "RL (Reparo de bordo)"], "Reparo localizado / Micro"),
        (["Micro(1,5)", "RL (Reparo de bordo)", "RL (Tapa-buraco)"], "Reparo localizado / Micro"),
        (["CBUQ (4)", "RL (Reparo de bordo)", "RL (Tapa-buraco)"], "Reforço"),
        (["CBUQ (8)", "RL (Reparo de bordo)", "RL (Tapa-buraco)"], "Reforço"),
        # Fresagem + reforço adicional: o reforço é mais severo e leva o laranja.
        (["FR(11) + CBUQ (11)", "Drenagem", "CBUQ (4)", "RL (Tapa-buraco)"], "Reforço"),
        (["FR(17) + CBUQ (17)", "Drenagem", "CBUQ (4)", "RL (Tapa-buraco)"], "Reforço"),
    ]
    for itens, esperado in casos:
        assert dnit_solution_family(itens) == esperado, itens


def test_reconstrucao_vence_todo_o_resto():
    assert dnit_solution_family(["Reconstrução", "Drenagem", "Tapa-buraco", "CBUQ (4)"]) == "Reconstrução"


def test_segmento_so_com_drenagem_nao_herda_cor_de_pavimento():
    """Não acontece na base atual (drenagem sempre vem acompanhada), mas outra base
    pode ter — e o trecho não pode sair amarelo por acidente."""
    assert dnit_solution_family(["Drenagem"]) == "Outras soluções"
    assert dnit_solution_family([]) == "Outras soluções"


# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

def test_paleta_bate_com_a_do_paragon():
    assert DNIT_FAMILY_COLORS["Reconstrução"] == VERMELHO
    assert DNIT_FAMILY_COLORS["Reforço"] == LARANJA
    assert DNIT_FAMILY_COLORS["Fresagem e recomposição"] == AMARELO
    assert DNIT_FAMILY_COLORS["Reparo localizado / Micro"] == VERDE


def test_rl_e_micro_compartilham_o_verde():
    """Decisão do cliente: uma cor só para RL e RL+Micro."""
    assert dnit_family_color(dnit_solution_family(["RL (Tapa-buraco)"])) == VERDE
    assert dnit_family_color(dnit_solution_family(["Micro(1,5)", "RL (Tapa-buraco)"])) == VERDE


def test_reforco_e_fresagem_mais_reforco_compartilham_o_laranja():
    assert dnit_family_color(dnit_solution_family(["CBUQ (4)"])) == LARANJA
    assert dnit_family_color(dnit_solution_family(["FR(11) + CBUQ (11)", "CBUQ (4)"])) == LARANJA


def test_cor_desconhecida_cai_no_neutro():
    assert dnit_family_color("Família Inexistente") == DNIT_FAMILY_COLORS["Outras soluções"]


# ---------------------------------------------------------------------------
# Cor pelo RÓTULO (gráficos e PDF) tem de bater com a cor pelo tipoId (mapa)
# ---------------------------------------------------------------------------

def _cor_do_rotulo(label):
    import app

    return app._dnit_solution_label_color(label)


def test_fresagem_com_recomposicao_e_amarela_no_grafico():
    """`FR4 + CBUQ(4)` é UMA intervenção (tipo "Fresagem e recomposição") — o CBUQ
    ali é a recomposição da fresagem, não um reforço somado.

    Uma versão anterior de `_dnit_solution_label_color` partia o rótulo em " + " e
    pegava a família mais severa entre as partes; o "CBUQ(4)" isolado virava Reforço
    e a barra saía LARANJA no gráfico de custos, enquanto o mapa — que classifica
    pelo `tipoId` do banco — pintava o mesmo trecho de amarelo."""
    assert _cor_do_rotulo("FR4 + CBUQ(4)") == AMARELO
    assert _cor_do_rotulo("FR(11) + CBUQ (11)") == AMARELO
    assert _cor_do_rotulo("FR(17) + CBUQ (17)") == AMARELO
    assert _cor_do_rotulo("FR5 + CBUQ(3) + CBUQ(4)") == AMARELO


def test_cbuq_avulso_continua_laranja_no_grafico():
    """A correção acima não pode transformar reforço em fresagem."""
    assert _cor_do_rotulo("CBUQ (4)") == LARANJA
    assert _cor_do_rotulo("CBUQ (8)") == LARANJA


def test_rotulos_de_conservacao_e_reconstrucao_no_grafico():
    assert _cor_do_rotulo("Micro(1,5)") == VERDE
    assert _cor_do_rotulo("RL (Tapa-buraco)") == VERDE
    assert _cor_do_rotulo("REC8") == VERMELHO


def test_nome_de_familia_como_rotulo_usa_a_cor_direta():
    """O gráfico de distribuição agrupa por família; o rótulo já é o nome dela."""
    for familia, cor in DNIT_FAMILY_COLORS.items():
        assert _cor_do_rotulo(familia) == cor, familia


# ---------------------------------------------------------------------------
# Trecho sem intervenção: "OK" em azul, para o mapa desenhar a rodovia inteira
# ---------------------------------------------------------------------------

def test_trecho_sem_obra_e_ok_azul():
    assert DNIT_FAMILY_NO_WORK == "OK"
    assert DNIT_FAMILY_COLORS["OK"] == AZUL


def test_ok_nunca_sai_do_classificador():
    """'OK' é preenchido por quem junta geometria e soluções, não deduzido de um
    nome de serviço — um tipo desconhecido tem de virar "Outras soluções", nunca OK."""
    assert dnit_family_from_type_name("Serviço Desconhecido") != DNIT_FAMILY_NO_WORK
    assert dnit_solution_family([]) != DNIT_FAMILY_NO_WORK
    assert dnit_solution_family(["Drenagem"]) != DNIT_FAMILY_NO_WORK


def test_ok_fica_no_fim_da_legenda():
    """A legenda segue a ordem de severidade; o trecho sem obra é o último."""
    assert DNIT_FAMILY_ORDER[-1] == DNIT_FAMILY_NO_WORK
    assert DNIT_FAMILY_ORDER[0] == "Reconstrução"
