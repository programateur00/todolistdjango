"""
Comando de gestión: hace una copia de seguridad de db.sqlite3 dentro
del propio proyecto, en una carpeta `backups/` (fuera de git — ver
.gitignore).

Por qué con la API de backup de sqlite3 y no un simple `cp`: la app
puede estar sirviendo peticiones mientras corre este comando (typical
uso: una tarea programada). Copiar el archivo tal cual mientras SQLite
está escribiendo puede dejar una copia a medias/corrupta. La API
`sqlite3.Connection.backup()` hace un volcado consistente aunque haya
escrituras en marcha, así que es la forma correcta de hacerlo.

Qué NO resuelve esto: la copia queda en el mismo disco que la base de
datos original. Protege de "he borrado una fila sin querer" o "una
migración salió mal", pero NO de perder la cuenta de PythonAnywhere
entera. Si en algún momento hay datos que de verdad importa no perder,
hay que bajarse la carpeta `backups/` de vez en cuando a otro sitio
(a mano, o con una tarea que la suba a otro lado).

Uso:
    python manage.py backup_db                # copia + limpia backups viejos
    python manage.py backup_db --keep 30       # conserva las últimas 30 (por defecto 14)
    python manage.py backup_db --dry-run       # enseña qué haría, sin tocar nada

Para que corra sola: pestaña "Tasks" de PythonAnywhere → programar
    cd /home/tu_usuario/tu_proyecto && python manage.py backup_db
una vez al día. (Las cuentas gratuitas creadas antes del 15-01-2026
tienen 1 tarea programada diaria incluida; en cuentas más nuevas o de
pago consulta tu plan.) Si no tienes tarea programada disponible, este
comando sigue siendo útil corriéndolo a mano antes de un cambio grande
(una migración, por ejemplo).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Copia db.sqlite3 a backups/ con marca de tiempo, y borra las copias más antiguas por encima de --keep."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", type=int, default=14,
            help="Cuántas copias recientes conservar (por defecto 14). Las más antiguas por encima de ese número se borran.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo enseña qué haría (copiar + qué se borraría), sin tocar nada.",
        )

    def handle(self, *args, **options):
        db_conf = settings.DATABASES["default"]
        if db_conf["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError(
                "Este comando solo sabe hacer copias de SQLite — la base de datos configurada no lo es."
            )

        source_path = Path(db_conf["NAME"])
        if not source_path.exists():
            raise CommandError(f"No encuentro la base de datos en {source_path}")

        backups_dir = Path(settings.BASE_DIR) / "backups"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_path = backups_dir / f"db_{stamp}.sqlite3"

        keep = options["keep"]
        dry_run = options["dry_run"]

        existing = sorted(backups_dir.glob("db_*.sqlite3")) if backups_dir.exists() else []

        if dry_run:
            self.stdout.write(f"(--dry-run) Copiaría {source_path} → {dest_path}")
            to_delete = existing[: max(0, len(existing) + 1 - keep)]
            if to_delete:
                self.stdout.write(f"(--dry-run) Borraría {len(to_delete)} copia(s) antigua(s):")
                for p in to_delete:
                    self.stdout.write(f"  {p.name}")
            else:
                self.stdout.write("(--dry-run) No hay copias antiguas que borrar todavía.")
            return

        backups_dir.mkdir(parents=True, exist_ok=True)

        # Volcado consistente vía la API de backup de sqlite3 (no un
        # simple cp) — ver docstring del módulo.
        source_conn = sqlite3.connect(str(source_path))
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            with dest_conn:
                source_conn.backup(dest_conn)
        finally:
            source_conn.close()
            dest_conn.close()

        self.stdout.write(self.style.SUCCESS(f"Copia guardada: {dest_path}"))

        # Limpieza: conserva las `keep` más recientes (incluyendo la que
        # acabamos de crear), borra el resto.
        all_backups = sorted(backups_dir.glob("db_*.sqlite3"))
        to_delete = all_backups[: max(0, len(all_backups) - keep)]
        for p in to_delete:
            p.unlink()
        if to_delete:
            self.stdout.write(f"Borradas {len(to_delete)} copia(s) antigua(s) por encima del límite de {keep}.")
        self.stdout.write(f"Copias guardadas ahora mismo: {len(all_backups) - len(to_delete)}")
