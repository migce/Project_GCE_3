import os
import json
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS, connection


EXCLUDES_DEFAULT = [
    # Core noisy apps/records recreated by migrations
    'contenttypes',
    'auth.permission',
    'admin.logentry',
    'sessions.session',
    # Project logs
    'main.mt5connectionlog',
    'main.mt5connectionhealth',
    'main.marketimporterror',
    'main.signalexecutionlog',
]


class Command(BaseCommand):
    help = "Import data from a legacy SQLite file into the current database (excludes logs)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sqlite', dest='sqlite_path', default=None,
            help='Path to legacy SQLite file (defaults to project BASE_DIR/db.sqlite3)'
        )
        parser.add_argument(
            '--output', dest='output', default=None,
            help='Optional path to write intermediate dump JSON (will be removed if omitted)'
        )
        parser.add_argument(
            '--keep-dump', action='store_true', default=False,
            help='Keep intermediate dump file (for debugging)'
        )
        parser.add_argument(
            '--exclude', action='append', default=[],
            help='Extra dotted app_label.Model or app_label to exclude (can be used multiple times)'
        )
        parser.add_argument(
            '--replace-auth', action='store_true', default=False,
            help='Replace auth users/groups in target DB with ones from SQLite (drops existing auth_user/auth_group and M2M links)'
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        sqlite_path = options['sqlite_path'] or str(base_dir / 'db.sqlite3')
        dump_path_opt = options['output']
        keep_dump = bool(options['keep_dump'])
        excludes = list(EXCLUDES_DEFAULT) + list(options['exclude'] or [])
        replace_auth = bool(options.get('replace_auth'))

        sqlite_path = os.path.abspath(os.path.expanduser(sqlite_path))
        if not os.path.exists(sqlite_path):
            raise CommandError(f"SQLite file not found: {sqlite_path}")

        self.stdout.write(self.style.NOTICE(f"Using legacy SQLite: {sqlite_path}"))
        self.stdout.write(self.style.NOTICE(f"Target database alias: '{DEFAULT_DB_ALIAS}' ({settings.DATABASES[DEFAULT_DB_ALIAS]['ENGINE']})"))

        # Inject a temporary 'legacy' database connection pointing to the SQLite file
        legacy_alias = 'legacy'
        legacy_conf = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
            'OPTIONS': {'timeout': 60},
        }
        settings.DATABASES[legacy_alias] = legacy_conf
        connections.databases[legacy_alias] = legacy_conf

        # Prepare dump target
        tmp_file = None
        if dump_path_opt:
            dump_file_path = dump_path_opt
            dump_dir = os.path.dirname(dump_file_path) or '.'
            os.makedirs(dump_dir, exist_ok=True)
        else:
            tmp_file = tempfile.NamedTemporaryFile(prefix='sqlite_export_', suffix='.json', delete=False)
            dump_file_path = tmp_file.name
            tmp_file.close()

        # Auth handling: either replace or auto-exclude if already present
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT COUNT(1) FROM auth_user")
                has_users = (cur.fetchone() or [0])[0] > 0
            with connection.cursor() as cur:
                cur.execute("SELECT COUNT(1) FROM auth_group")
                has_groups = (cur.fetchone() or [0])[0] > 0
        except Exception:
            has_users = has_groups = False

        if replace_auth:
            # Ensure we DO include auth.user/group in dump
            if 'auth.user' in excludes:
                excludes.remove('auth.user')
            if 'auth.group' in excludes:
                excludes.remove('auth.group')
            self.stdout.write(self.style.WARNING("Will replace auth users/groups in target DB."))
        else:
            # If target has them already, exclude to avoid conflicts
            if has_users and 'auth.user' not in excludes:
                excludes.append('auth.user')
                self.stdout.write(self.style.WARNING("Target has users; excluding auth.user from dump to avoid conflicts (use --replace-auth to override)"))
            if has_groups and 'auth.group' not in excludes:
                excludes.append('auth.group')
                self.stdout.write(self.style.WARNING("Target has groups; excluding auth.group from dump to avoid conflicts (use --replace-auth to override)"))

        self.stdout.write(self.style.NOTICE(f"Dumping legacy data to: {dump_file_path}"))

        # Dump from legacy
        dumped = False
        try:
            with open(dump_file_path, 'w', encoding='utf-8') as fh:
                # Prefer direct call if available (Django >=3.2 uses options names 'use_natural_*')
                call_command(
                    'dumpdata',
                    database=legacy_alias,
                    use_natural_foreign_keys=True,
                    use_natural_primary_keys=True,
                    indent=2,
                    exclude=excludes,
                    stdout=fh,
                )
                dumped = True
        except Exception as e:
            # Fallback: run a subprocess with SQLite as default DB (unset DATABASE_URL)
            import sys
            import subprocess
            env_sqlite = os.environ.copy()
            env_sqlite.pop('DATABASE_URL', None)
            env_sqlite['DJANGO_SKIP_DOTENV'] = '1'
            cmd = [
                sys.executable,
                str(base_dir / 'manage.py'),
                'dumpdata',
                '--indent', '2',
                '--natural-foreign',
                '--natural-primary',
            ]
            for item in excludes:
                cmd.extend(['--exclude', item])
            try:
                with open(dump_file_path, 'w', encoding='utf-8') as fh:
                    proc = subprocess.run(cmd, cwd=str(base_dir), env=env_sqlite, stdout=fh, stderr=subprocess.PIPE, text=True)
                if proc.returncode != 0:
                    raise CommandError(f"Subprocess dumpdata failed (rc={proc.returncode}): {proc.stderr.strip()}")
                dumped = True
            except Exception as se:
                raise CommandError(f"Unable to serialize database (both direct and subprocess methods failed): {se}")

        # Show quick stats about what will be loaded
        try:
            with open(dump_file_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            total = len(data) if isinstance(data, list) else 0
            by_model = {}
            if isinstance(data, list):
                for obj in data:
                    m = obj.get('model')
                    by_model[m] = by_model.get(m, 0) + 1
            # Print top models counts (up to 10)
            top = sorted(by_model.items(), key=lambda kv: kv[1], reverse=True)[:10]
            self.stdout.write(self.style.NOTICE(f"Dump contains {total} objects; top models:"))
            for m, c in top:
                self.stdout.write(f"  - {m}: {c}")
        except Exception:
            pass

        # Load into current default database
        # Optionally wipe auth tables before load
        if replace_auth and (has_users or has_groups):
            self.stdout.write(self.style.WARNING("Clearing existing auth tables in target DB..."))
            with connection.cursor() as cur:
                cur.execute("DELETE FROM auth_user_user_permissions;")
                cur.execute("DELETE FROM auth_user_groups;")
                cur.execute("DELETE FROM auth_group_permissions;")
                cur.execute("DELETE FROM auth_user;")
                cur.execute("DELETE FROM auth_group;")

        self.stdout.write(self.style.NOTICE("Loading data into target database..."))
        call_command('loaddata', dump_file_path, database=DEFAULT_DB_ALIAS)

        # Reset sequences to avoid key collisions for apps with integer PKs
        apps = ['main', 'auth', 'admin', 'sessions', 'contenttypes']
        try:
            engine = (settings.DATABASES[DEFAULT_DB_ALIAS]['ENGINE'] or '').lower()
        except Exception:
            engine = ''

        # Robust sequence reset for PostgreSQL by introspecting Django models
        if 'postgres' in engine:
            from django.apps import apps as django_apps
            from django.db.models import AutoField, BigAutoField, SmallAutoField
            self.stdout.write(self.style.NOTICE('Resetting sequences (PostgreSQL)...'))
            with connection.cursor() as cur:
                for model in django_apps.get_models():
                    if model._meta.app_label not in apps:
                        # apps variable above is a list of app labels we care about
                        continue
                    pk = model._meta.pk
                    if not isinstance(pk, (AutoField, BigAutoField, SmallAutoField)):
                        continue
                    table = model._meta.db_table
                    pkcol = pk.column
                    try:
                        cur.execute(
                            f"SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE(MAX(\"{pkcol}\"), 1), MAX(\"{pkcol}\") IS NOT NULL) FROM \"{table}\";",
                            [table, pkcol],
                        )
                    except Exception as e:
                        # Non-fatal: continue with other tables
                        self.stdout.write(self.style.WARNING(f"  Skip sequence for {table}: {e}"))
            self.stdout.write(self.style.SUCCESS('Sequences reset attempt finished.'))
        else:
            self.stdout.write(self.style.WARNING('Sequence reset skipped (not PostgreSQL).'))

        self.stdout.write(self.style.SUCCESS("Import completed successfully."))

        # Cleanup temp file
        if tmp_file is not None and not keep_dump:
            try:
                os.unlink(dump_file_path)
            except Exception:
                pass
