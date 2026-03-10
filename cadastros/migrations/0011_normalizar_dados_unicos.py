# Normaliza dados para unicidade: Cargo.nome, Viajante (nome, cpf, rg, telefone), Veiculo.placa

import re

from django.db import migrations


def only_digits(s):
    if s is None:
        return ''
    return re.sub(r'\D', '', str(s))


def normalizar(apps, schema_editor):
    Cargo = apps.get_model('cadastros', 'Cargo')
    Viajante = apps.get_model('cadastros', 'Viajante')
    Veiculo = apps.get_model('cadastros', 'Veiculo')

    for c in Cargo.objects.all():
        if c.nome:
            c.nome = ' '.join(c.nome.strip().upper().split())
            c.save(update_fields=['nome'])

    for v in Viajante.objects.all():
        atualizado = False
        if v.nome:
            novo_nome = ' '.join(v.nome.strip().upper().split())
            if v.nome != novo_nome:
                v.nome = novo_nome
                atualizado = True
        if v.cpf:
            d = only_digits(v.cpf)
            if d and v.cpf != d:
                v.cpf = d
                atualizado = True
        if v.rg and v.rg != 'NAO POSSUI RG':
            d = only_digits(v.rg)
            if v.rg != d:
                v.rg = d or v.rg
                atualizado = True
        if v.telefone:
            d = only_digits(v.telefone)
            if d and v.telefone != d:
                v.telefone = d
                atualizado = True
        if atualizado:
            v.save(update_fields=['nome', 'cpf', 'rg', 'telefone'])

    for veic in Veiculo.objects.all():
        if veic.placa:
            nova = re.sub(r'[\s\-]', '', veic.placa.strip().upper())
            if veic.placa != nova:
                veic.placa = nova
                veic.save(update_fields=['placa'])


def reverter(apps, schema_editor):
    pass  # Não revertível


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0010_cargo_is_padrao_remove_ativo'),
    ]

    operations = [
        migrations.RunPython(normalizar, reverter),
    ]
