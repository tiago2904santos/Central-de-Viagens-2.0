import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from cadastros.models import Cidade
from cadastros.services_importacao import importar_cidades_csv


class ImportacaoCidadesCsvTests(TestCase):
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

    def test_formato_municipio_code_separador_ponto_virgula(self):
        p = self._write_csv("id_municipio;uf;municipio;longitude;latitude\n1;pr;curitiba;-25;-49\n2;pr;LONDRINA;-23;-51\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 2)
        self.assertEqual(r.existentes, 0)
        self.assertTrue(Cidade.objects.filter(nome="CURITIBA", uf="PR").exists())
        self.assertTrue(Cidade.objects.filter(nome="LONDRINA", uf="PR").exists())

    def test_formato_nome_uf_virgula(self):
        p = self._write_csv("nome,uf\nMaringá,pr\n", suffix=".csv")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 1)
        c = Cidade.objects.get(uf="PR")
        self.assertEqual(c.nome, "MARINGÁ")

    def test_formato_cidade_uf(self):
        p = self._write_csv("cidade,uf\nFoz do Iguaçu,pr\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 1)
        self.assertTrue(Cidade.objects.filter(nome="FOZ DO IGUAÇU", uf="PR").exists())

    def test_formato_municipio_uf(self):
        p = self._write_csv("municipio,uf\nCascavel,pr\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 1)

    def test_nao_duplica_existente(self):
        Cidade.objects.create(nome="PONTA GROSSA", uf="PR")
        p = self._write_csv("municipio;uf\nPONTA GROSSA;pr\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 0)
        self.assertEqual(r.existentes, 1)
        self.assertEqual(Cidade.objects.filter(nome="PONTA GROSSA", uf="PR").count(), 1)

    def test_uf_invalida_gera_erro_linha(self):
        p = self._write_csv("municipio;uf\nXaxim;PRS\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 0)
        self.assertEqual(len([e for e in r.erros if e[0] > 0]), 1)

    def test_linha_vazia_ignorada(self):
        p = self._write_csv("municipio;uf\n;;\nJoinville;sc\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.ignoradas, 1)
        self.assertEqual(r.criadas, 1)

    def test_dry_run_nao_persiste(self):
        p = self._write_csv("municipio;uf\nBlumenau;sc\n")
        n = Cidade.objects.count()
        r = importar_cidades_csv(p, dry_run=True)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 1)
        self.assertEqual(Cidade.objects.count(), n)

    def test_comando_dry_run(self):
        p = self._write_csv("municipio;uf\nChapecó;sc\n")
        n = Cidade.objects.count()
        buf = StringIO()
        call_command("importar_cidades", str(p), "--dry-run", stdout=buf)
        p.unlink(missing_ok=True)
        self.assertIn("simulação", buf.getvalue().lower())
        self.assertEqual(Cidade.objects.count(), n)

    def test_arquivo_inexistente_comando(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("importar_cidades", "/caminho/que/nao/existe_import.csv")
        self.assertIn("não encontrado", str(ctx.exception).lower())

    def test_duplicata_no_proprio_arquivo(self):
        p = self._write_csv("municipio;uf\nAPUCARANA;pr\nAPUCARANA;pr\n")
        r = importar_cidades_csv(p, dry_run=False)
        p.unlink(missing_ok=True)
        self.assertEqual(r.criadas, 1)
        self.assertEqual(r.ignoradas, 1)

    def test_service_arquivo_inexistente(self):
        r = importar_cidades_csv("/nada/nada.csv", dry_run=True)
        self.assertTrue(any("não encontrado" in m for _ln, m in r.erros if _ln == 0))
