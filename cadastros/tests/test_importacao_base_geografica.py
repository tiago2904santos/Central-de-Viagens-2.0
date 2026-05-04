import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.services_importacao import importar_base_geografica
from cadastros.services_importacao import importar_cidades_csv
from cadastros.services_importacao import importar_estados_csv
class ImportacaoBaseGeograficaTests(TestCase):
    def _write_csv(self, content: str, suffix: str = ".csv") -> Path:
        t = tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix=suffix,
            encoding="utf-8-sig",
            newline="",
        )
        try:
            t.write(content)
        finally:
            t.close()
        return Path(t.name)

    def test_importa_estados_csv_normaliza_e_nao_duplica(self):
        estados = self._write_csv(
            "COD,NOME,SIGLA\n"
            "41,Paraná,PR\n"
            "41,PARANÁ,PR\n",
        )
        r = importar_estados_csv(estados, dry_run=False)
        estados.unlink(missing_ok=True)
        self.assertEqual(r.total_linhas, 2)
        self.assertEqual(Estado.objects.filter(sigla="PR").count(), 1)
        e = Estado.objects.get(sigla="PR")
        self.assertEqual(e.nome, "PARANÁ")
        self.assertGreaterEqual(r.existentes, 1)

    def test_importar_base_geografica_municipio_code_vincula_estado_capital_e_coords(self):
        e_est = self._write_csv(
            "COD,NOME,SIGLA\n"
            "41,PARANÁ,PR\n",
        )
        mun = self._write_csv(
            "id_municipio;uf;municipio;longitude;latitude\n"
            "4106902;PR;Curitiba;-49.2733;-25.4284\n"
            "4113700;PR;Londrina;-51.1628;-23.3045\n",
        )
        r = importar_base_geografica(
            e_est,
            municipios_code_path=mun,
            dry_run=False,
        )
        e_est.unlink(missing_ok=True)
        mun.unlink(missing_ok=True)

        est_pr = Estado.objects.get(sigla="PR")
        cur = Cidade.objects.get(codigo_ibge=4106902)
        lon = Cidade.objects.get(codigo_ibge=4113700)
        self.assertEqual(cur.estado_id, est_pr.pk)
        self.assertEqual(cur.uf, "PR")
        self.assertTrue(cur.capital)
        self.assertFalse(lon.capital)
        self.assertEqual(lon.estado_id, est_pr.pk)

    def test_importar_municipios_ibge_alternativa(self):
        e_est = self._write_csv(
            "COD,NOME,SIGLA\n"
            "41,PARANÁ,PR\n",
        )
        m_ibge = self._write_csv(
            "COD UF,COD,NOME\n"
            "41,4106902,CURITIBA\n",
        )
        r = importar_base_geografica(
            e_est,
            municipios_ibge_path=m_ibge,
            dry_run=False,
        )
        e_est.unlink(missing_ok=True)
        m_ibge.unlink(missing_ok=True)

        self.assertGreaterEqual(r.cidades.criadas, 1)
        c = Cidade.objects.get(nome="CURITIBA")
        self.assertEqual(c.estado.sigla, "PR")
        self.assertTrue(c.capital)

    def test_nao_duplica_cidade_nome_mais_estado(self):
        est_pr, _ = Estado.objects.get_or_create(
            sigla="PR",
            defaults={"nome": "PARANÁ", "codigo_ibge": 41},
        )
        Cidade.objects.create(nome="MARINGÁ", estado=est_pr)
        mun = self._write_csv(
            "id_municipio;uf;municipio\n"
            "4115200;PR;Maringá\n",
        )
        r = importar_cidades_csv(mun, dry_run=False, fonte_municipio_code=True)
        mun.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 0)
        self.assertGreaterEqual(r.existentes, 1)
        self.assertEqual(Cidade.objects.filter(nome="MARINGÁ", estado=est_pr).count(), 1)

    def test_dry_run_base_geografica_nao_persiste(self):
        e_est = self._write_csv("COD,NOME,SIGLA\n41,PARANÁ,PR\n")
        mun = self._write_csv("id_municipio;uf;municipio\n4106902;PR;Curitiba\n")
        n_e, n_c = Estado.objects.count(), Cidade.objects.count()
        r = importar_base_geografica(e_est, municipios_code_path=mun, dry_run=True)
        e_est.unlink(missing_ok=True)
        mun.unlink(missing_ok=True)
        self.assertGreater(r.estados.criados + r.estados.existentes, 0)
        self.assertGreater(r.cidades.criadas, 0)
        self.assertEqual(Estado.objects.count(), n_e)
        self.assertEqual(Cidade.objects.count(), n_c)

    def test_comando_importar_base_geografica_dry_run(self):
        e_est = self._write_csv("COD,NOME,SIGLA\n41,PARANÁ,PR\n")
        mun = self._write_csv("id_municipio;uf;municipio\n4106902;PR;Curitiba\n")
        n_c = Cidade.objects.count()
        buf = StringIO()
        call_command(
            "importar_base_geografica",
            "--estados",
            str(e_est),
            "--municipios-code",
            str(mun),
            "--dry-run",
            stdout=buf,
        )
        e_est.unlink(missing_ok=True)
        mun.unlink(missing_ok=True)
        out = buf.getvalue().lower()
        self.assertIn("estados", out)
        self.assertIn("cidades", out)
        self.assertEqual(Cidade.objects.count(), n_c)

    def test_comando_arquivo_municipios_inexistente(self):
        e_est = self._write_csv("COD,NOME,SIGLA\n41,PARANÁ,PR\n")
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "importar_base_geografica",
                "--estados",
                str(e_est),
                "--municipios-code",
                "/caminho/inexistente_mun.csv",
            )
        self.assertIn("não encontrado", str(ctx.exception).lower())
        e_est.unlink(missing_ok=True)

    def test_simple_csv_sem_estado_cadastrado_gera_erro_linha(self):
        mun = self._write_csv("nome,uf\nCidade Orfa,ZZ\n")
        r = importar_cidades_csv(mun, dry_run=False)
        mun.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 0)
        self.assertTrue(any("não cadastrado" in m for _ln, m in r.erros if _ln > 0))
