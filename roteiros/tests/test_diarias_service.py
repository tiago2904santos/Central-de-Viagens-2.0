from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from roteiros import roteiro_logic
from roteiros.services.diarias import (
    PeriodMarker,
    TABELA_DIARIAS,
    calculate_periodized_diarias,
)


class DiariasServiceTests(TestCase):
    def test_periodizacao_inclui_percentual_30_no_retorno_final(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 4, 10, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 4, 19, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "3 x 100% + 1 x 30%")
        expected_total = (TABELA_DIARIAS["CAPITAL"]["24h"] * 3) + TABELA_DIARIAS["CAPITAL"]["30"]
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_periodizacao_preserva_percentuais_15_e_30(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 4, 15, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 4, 23, 30),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "3 x 100% + 1 x 15% + 1 x 30%")

    def test_periodizacao_sem_percentual_complementar(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 3, 8, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 3, 12, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "2 x 100%")

    def test_calculo_avulso_considera_retorno_final_manual(self):
        state = {
            "roteiro_modo": roteiro_logic.ROTEIRO_MODO_PROPRIO,
            "sede_estado_id": None,
            "sede_cidade_id": None,
            "trechos": [
                {
                    "saida_data": "2026-05-01",
                    "saida_hora": "08:00",
                    "destino_cidade_id": None,
                    "destino_estado_id": None,
                    "destino_nome": "FLORIANOPOLIS/SC",
                },
                {
                    "saida_data": "2026-05-04",
                    "saida_hora": "10:00",
                    "destino_cidade_id": None,
                    "destino_estado_id": None,
                    "destino_nome": "CURITIBA/PR",
                },
            ],
            "retorno": {
                "chegada_data": "2026-05-04",
                "chegada_hora": "19:00",
            },
        }
        resultado = roteiro_logic._calculate_avulso_diarias_from_state(state)
        self.assertIn("1 x 30%", resultado["totais"]["total_diarias"])
        self.assertGreaterEqual(resultado["totais"]["total_valor_decimal"], Decimal("0.01"))
