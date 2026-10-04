from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_phone'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='phone',
            new_name='contact_number',
        ),
    ]