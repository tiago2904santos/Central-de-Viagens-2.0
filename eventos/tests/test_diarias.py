"""
Testes do serviço de diárias, incluindo regra de pernoites.
"""
from datetime import datetime

from django.test import TestCase

from eventos.services.diarias import (
    PeriodMarker,
    TABELA_DIARIAS,
    count_pernoites,
    calculate_periodized_diarias,
    build_periods,
)


class CountPernoitesTests(TestCase):
    """Testes da função count_pernoites."""

    def test_zero_pernoites_mesmo_dia(self):
        saida = datetime(2026, 3, 15, 6, 0)
        chegada = datetime(2026, 3, 15, 23, 0)
        self.assertEqual(count_pernoites(saida, chegada), 0)

    def test_um_pernoite(self):
        saida = datetime(2026, 3, 15, 14, 0)
        chegada = datetime(2026, 3, 16, 11, 30)
        self.assertEqual(count_pernoites(saida, chegada), 1)

    def test_dois_pernoites(self):
        saida = datetime(2026, 3, 15, 14, 0)
        chegada = datetime(2026, 3, 17, 11, 30)
        self.assertEqual(count_pernoites(saida, chegada), 2)

    def test_tres_pernoites_caso_principal(self):
        """Caso: saída 15/03 14:00, retorno 18/03 11:30 → 3 pernoites (15→16, 16→17, 17→18)."""
        saida = datetime(2026, 3, 15, 14, 0)
        chegada = datetime(2026, 3, 18, 11, 30)
        self.assertEqual(count_pernoites(saida, chegada), 3)

    def test_chegada_antes_saida_retorna_zero(self):
        saida = datetime(2026, 3, 18, 14, 0)
        chegada = datetime(2026, 3, 15, 11, 0)
        self.assertEqual(count_pernoites(saida, chegada), 0)

    def test_chegada_mesmo_dia_retorna_zero(self):
        saida = datetime(2026, 3, 15, 8, 0)
        chegada = datetime(2026, 3, 15, 20, 0)
        self.assertEqual(count_pernoites(saida, chegada), 0)


class DiariasPernoitesIntegrationTests(TestCase):
    """
    Testes de integração: cálculo de diárias com regra de pernoites.
    Um único marcador = um trecho (sede → destino → retorno à sede).
    """

    def _calc(self, saida_sede, chegada_destino, saida_destino, chegada_sede, cidade='Interior', uf='PR'):
        """Um trecho: saída da sede, chegada ao destino, saída do destino, chegada à sede."""
        marker = PeriodMarker(saida=saida_sede, destino_cidade=cidade, destino_uf=uf)
        return calculate_periodized_diarias(
            [marker],
            chegada_sede,
            quantidade_servidores=1,
        )

    def test_caso_principal_tres_pernoites(self):
        """
        Saída sede 15/03 14:00, chegada destino 15/03 17:30, saída destino 18/03 08:00,
        chegada sede 18/03 11:30. Esperado: 3 x 100%.
        """
        saida_sede = datetime(2026, 3, 15, 14, 0)
        chegada_destino = datetime(2026, 3, 15, 17, 30)
        saida_destino = datetime(2026, 3, 18, 8, 0)
        chegada_sede = datetime(2026, 3, 18, 11, 30)
        # O serviço usa apenas o primeiro marcador (saída da sede) e a chegada final à sede
        marker = PeriodMarker(saida=saida_sede, destino_cidade='Interior', destino_uf='PR')
        resultado = calculate_periodized_diarias([marker], chegada_sede, quantidade_servidores=1)
        self.assertEqual(resultado['totais']['total_diarias'], '3 x 100%')
        valor_esperado = TABELA_DIARIAS['INTERIOR']['24h'] * 3  # 871,65
        self.assertEqual(
            resultado['totais']['total_valor'],
            '871,65',
            msg=f"Esperado 3 x 290,55 = 871,65, obtido {resultado['totais']['total_valor']}",
        )

    def test_um_pernoite_uma_diaria_integral(self):
        """Saída 15/03 14:00, retorno 16/03 11:30 → 1 x 100%."""
        saida_sede = datetime(2026, 3, 15, 14, 0)
        chegada_sede = datetime(2026, 3, 16, 11, 30)
        marker = PeriodMarker(saida=saida_sede, destino_cidade='Interior', destino_uf='PR')
        resultado = calculate_periodized_diarias([marker], chegada_sede, quantidade_servidores=1)
        self.assertEqual(resultado['totais']['total_diarias'], '1 x 100%')

    def test_dois_pernoites_duas_integrais(self):
        """Saída 15/03 14:00, retorno 17/03 11:30 → 2 x 100%."""
        saida_sede = datetime(2026, 3, 15, 14, 0)
        chegada_sede = datetime(2026, 3, 17, 11, 30)
        marker = PeriodMarker(saida=saida_sede, destino_cidade='Interior', destino_uf='PR')
        resultado = calculate_periodized_diarias([marker], chegada_sede, quantidade_servidores=1)
        self.assertEqual(resultado['totais']['total_diarias'], '2 x 100%')

    def test_sem_pernoite_mantem_regra_por_horas(self):
        """Saída 15/03 06:00, retorno 15/03 23:00 → sem forçar diária integral por pernoite."""
        saida_sede = datetime(2026, 3, 15, 6, 0)
        chegada_sede = datetime(2026, 3, 15, 23, 0)
        marker = PeriodMarker(saida=saida_sede, destino_cidade='Interior', destino_uf='PR')
        resultado = calculate_periodized_diarias([marker], chegada_sede, quantidade_servidores=1)
        # 17 horas: 0 dias inteiros + fração (30% ou 15% conforme regra)
        self.assertIn('total_diarias', resultado['totais'])
        # Não deve ser "1 x 100%" por pernoite, pois não há pernoite
        self.assertNotEqual(resultado['totais']['total_diarias'], '1 x 100%')

    def test_calculo_por_horas_maior_que_pernoites_mantem_maior(self):
        """Se o cálculo por horas já der mais diárias integrais que pernoites, mantém o maior."""
        # Ex.: 4 dias e 10 horas fora → 4 inteiras + fração. 3 pernoites. Máximo(4, 3) = 4.
        saida_sede = datetime(2026, 3, 15, 8, 0)
        chegada_sede = datetime(2026, 3, 19, 18, 0)  # 4 dias e 10h
        marker = PeriodMarker(saida=saida_sede, destino_cidade='Interior', destino_uf='PR')
        resultado = calculate_periodized_diarias([marker], chegada_sede, quantidade_servidores=1)
        # 4 pernoites (15→16, 16→17, 17→18, 18→19). Cálculo por horas: 4 dias + 10h → 4 inteiras + 30%
        # Regra: full >= pernoites. 4 >= 4, não precisa ajustar. Deve ter 4 x 100% e possivelmente 1 x 30%
        self.assertIn('4 x 100%', resultado['totais']['total_diarias'])


class BuildPeriodsPernoitesTests(TestCase):
    """Testes de build_periods com ajuste de pernoites."""

    def test_tres_pernoites_gera_tres_integrais(self):
        saida = datetime(2026, 3, 15, 14, 0)
        chegada_sede = datetime(2026, 3, 18, 11, 30)
        marker = PeriodMarker(saida=saida, destino_cidade='Cidade', destino_uf='PR')
        periodos = build_periods([marker], chegada_sede, quantidade_servidores=1)
        self.assertEqual(len(periodos), 1)
        self.assertEqual(periodos[0]['n_diarias'], 3)
        self.assertEqual(periodos[0]['percentual_adicional'], 0)

    def test_bate_volta_diario_ignora_periodos_em_sede(self):
        markers = [
            PeriodMarker(saida=datetime(2026, 4, 23, 8, 0), destino_cidade='Colombo', destino_uf='PR'),
            PeriodMarker(saida=datetime(2026, 4, 23, 17, 30), destino_cidade='Curitiba', destino_uf='PR'),
            PeriodMarker(saida=datetime(2026, 4, 24, 8, 0), destino_cidade='Colombo', destino_uf='PR'),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 4, 24, 18, 10),
            quantidade_servidores=1,
            sede_cidade='Curitiba',
            sede_uf='PR',
        )

        self.assertEqual(resultado['totais']['total_diarias'], '2 x 30%')
        self.assertEqual(resultado['totais']['total_valor'], '174,34')
        self.assertEqual(len(resultado['periodos']), 2)
        self.assertTrue(all(periodo['tipo'] == 'INTERIOR' for periodo in resultado['periodos']))
