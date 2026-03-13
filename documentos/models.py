from django.db import models


class BaseDocumento(models.Model):
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField(blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo


class Oficio(BaseDocumento):
    pass


class Roteiro(BaseDocumento):
    origem = models.CharField(max_length=120, blank=True, default='')
    destino = models.CharField(max_length=120, blank=True, default='')


class PlanoTrabalho(BaseDocumento):
    pass


class OrdemServico(BaseDocumento):
    pass


class Justificativa(BaseDocumento):
    pass


class Termo(BaseDocumento):
    pass
