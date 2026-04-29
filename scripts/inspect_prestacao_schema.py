import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django

django.setup()

from django.db import connection

with connection.cursor() as cur:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'prestacao_contas_%'")
    print("tables", cur.fetchall())
    cur.execute("PRAGMA table_info('prestacao_contas_prestacaoconta')")
    print("prestacao_cols", cur.fetchall())
    cur.execute("PRAGMA table_info('prestacao_contas_relatoriotecnicoprestacao')")
    print("rt_cols", cur.fetchall())
