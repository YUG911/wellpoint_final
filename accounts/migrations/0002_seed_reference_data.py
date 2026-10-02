from django.db import migrations

def seed_reference_data(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    DayMaster = apps.get_model('accounts', 'DayMaster')
    for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin'):
        Role.objects.get_or_create(role_name=name)
    for name in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'):
        DayMaster.objects.get_or_create(day_name=name)

def reverse_seed_reference_data(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunPython(seed_reference_data, reverse_seed_reference_data)]
