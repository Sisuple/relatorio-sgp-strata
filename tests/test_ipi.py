import math

import pandas as pd

from services.ipi import calcular_ipi, calcular_ipi_lote


def test_icdp_muito_ruim_dqo_chega_a_1_pela_formula_multiplicativa():
    result = calcular_ipi(icds=5, icdp=1, vmdl=1000, vmdp=100, vmdeq_ref=1400)

    # Pela fórmula multiplicativa definida, DDP = 1 faz o DQObase chegar a 1.
    # Portanto o resultado correto da fórmula é 1, não 0,88.
    assert math.isclose(result["dqo"], 1.0, rel_tol=1e-9)
    assert result["gatilho"] == 0.88


def test_icds_muito_ruim_dqo_chega_a_1():
    result = calcular_ipi(icds=1, icdp=5, vmdl=1000, vmdp=100, vmdeq_ref=1400)

    assert math.isclose(result["dqo"], 1.0, rel_tol=1e-9)


def test_trafego_zero_ft_zero():
    result = calcular_ipi(icds=3, icdp=3, vmdl=0, vmdp=0, vmdeq_ref=1000)

    assert result["vmdeq"] == 0
    assert result["ft"] == 0
    assert result["ipi"] == 0


def test_icds_abaixo_de_1_satura_dano_sem_gerar_complexo():
    result = calcular_ipi(icds=0.3, icdp=1.6, vmdl=1000, vmdp=100, vmdeq_ref=1400)

    assert result["dds"] == 1
    assert isinstance(result["ipi"], float)


def test_vmdeq_muito_maior_que_referencia_satura_ft_em_1():
    result = calcular_ipi(icds=3, icdp=3, vmdl=50000, vmdp=10000, vmdeq_ref=1000)

    assert result["ft"] == 1


def test_calculo_em_lote_usa_percentil_95_do_vmdeq():
    df = pd.DataFrame(
        {
            "icds": [5, 3, 2],
            "icdp": [5, 3, 2],
            "vmdl": [100, 200, 300],
            "vmdp": [10, 20, 30],
        }
    )

    result = calcular_ipi_lote(df)
    expected_vmdeq = pd.Series([140, 280, 420]).quantile(0.95)

    assert list(result["vmdeq"]) == [140, 280, 420]
    assert result["ipi"].notna().all()
    assert expected_vmdeq > 0
    assert "classe_prioridade" in result.columns
