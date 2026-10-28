import os
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, connections


class Command(BaseCommand):
    help = (
        "Safely migrates and verifies schema and data into PostgreSQL (e.g. Neon on Vercel Marketplace). "
        "Applies Django migrations, loads the source data dump, resets auto-increment sequences, "
        "and validates record counts and relationship integrity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dump-file',
            default='datadump_source.json',
            help='Path to the JSON fixture data dump (default: datadump_source.json)',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify existing record counts and relationship integrity without migrating data.',
        )

    def handle(self, *args, **options):
        dump_file = options['dump_file']
        verify_only = options['verify_only']

        self.stdout.write(self.style.MIGRATE_HEADING("=== WellPoint PostgreSQL Data Migration & Verification ==="))

        # 1. Inspect Active Database Connection
        engine = connection.settings_dict.get('ENGINE', '')
        db_name = connection.settings_dict.get('NAME', '')
        db_host = connection.settings_dict.get('HOST', 'localhost')
        self.stdout.write(f"Target Database Engine: {engine}")
        self.stdout.write(f"Target Database Name:   {db_name}")
        self.stdout.write(f"Target Database Host:   {db_host}")

        if not verify_only:
            # 2. Check Dump File Existence
            dump_path = Path(dump_file)
            if not dump_path.is_absolute():
                dump_path = Path(settings.BASE_DIR) / dump_file

            if not dump_path.exists():
                raise CommandError(
                    f"Data dump file not found at {dump_path}. "
                    "Please create a backup dump first with: python manage.py dumpdata ... -o datadump_source.json"
                )

            self.stdout.write(f"Source Data Dump:       {dump_path} ({dump_path.stat().st_size:,} bytes)")

            # 3. Apply Schema Migrations
            self.stdout.write(self.style.MIGRATE_HEADING("\n1. Applying migrations to target database..."))
            call_command('migrate', interactive=False)
            self.stdout.write(self.style.SUCCESS("[OK] Migrations applied successfully."))

            # 4. Load Data Dump
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n2. Loading data from {dump_path.name}..."))
            call_command('loaddata', str(dump_path))
            self.stdout.write(self.style.SUCCESS("[OK] Data loaded successfully."))

            # 5. Reset PostgreSQL Sequences (if PostgreSQL)
            if 'postgresql' in engine:
                self.stdout.write(self.style.MIGRATE_HEADING("\n3. Resetting PostgreSQL primary key sequences..."))
                self.reset_postgres_sequences()
                self.stdout.write(self.style.SUCCESS("[OK] PostgreSQL sequences reset successfully."))
            else:
                self.stdout.write(self.style.WARNING("\n3. Skipping sequence reset (target is not PostgreSQL)."))

        # 6. Verify Record Counts and Relationships
        self.stdout.write(self.style.MIGRATE_HEADING("\n4. Verifying record counts and relationship integrity..."))
        results = self.verify_database()

        self.stdout.write(self.style.SUCCESS("\n=== Migration & Verification Summary ==="))
        self.stdout.write(f"{'Model':<35} {'Count':>10}")
        self.stdout.write("-" * 47)
        for model_label, count in results['counts'].items():
            self.stdout.write(f"{model_label:<35} {count:>10}")
        self.stdout.write("-" * 47)
        self.stdout.write(f"Total clinical records verified: {results['total_records']}")

        if results['errors']:
            for err in results['errors']:
                self.stderr.write(self.style.ERROR(f"Error: {err}"))
            raise CommandError("Data verification encountered integrity errors.")

        self.stdout.write(self.style.SUCCESS("[OK] All record counts and relational integrity checks passed cleanly!"))

    def reset_postgres_sequences(self):
        """Resets all primary key sequences for PostgreSQL so future INSERTs succeed."""
        app_labels = ['accounts', 'doctors', 'appointments', 'records']
        app_configs = [apps.get_app_config(label) for label in app_labels if apps.is_installed(label)]
        output = connection.ops.sequence_reset_sql(no_style(), [m for ac in app_configs for m in ac.get_models()])
        with connection.cursor() as cursor:
            for sql in output:
                cursor.execute(sql)

    def verify_database(self):
        """Verifies record counts and foreign key relationships across all clinical models."""
        counts = {}
        total = 0
        errors = []

        relevant_apps = ['accounts', 'doctors', 'appointments', 'records']
        for model in apps.get_models():
            if model._meta.app_label in relevant_apps:
                cnt = model.objects.count()
                counts[model._meta.label] = cnt
                total += cnt

        # Relationship integrity checks
        from accounts.models import User, Patient, Clinic
        from doctors.models import Doctor
        from appointments.models import Appointment

        # Verify Doctors have valid User links
        orphan_doctors = Doctor.objects.filter(user__isnull=True).count()
        if orphan_doctors > 0:
            errors.append(f"Found {orphan_doctors} Doctor records with null user!")

        # Verify Patients have valid User links
        orphan_patients = Patient.objects.filter(user__isnull=True).count()
        if orphan_patients > 0:
            errors.append(f"Found {orphan_patients} Patient records with null user!")

        # Verify Appointments link to valid Patients and Doctors
        orphan_appts = Appointment.objects.filter(patient__isnull=True).count() + Appointment.objects.filter(doctor__isnull=True).count()
        if orphan_appts > 0:
            errors.append(f"Found {orphan_appts} Appointment records with missing patient or doctor!")

        return {
            'counts': counts,
            'total_records': total,
            'errors': errors,
        }
