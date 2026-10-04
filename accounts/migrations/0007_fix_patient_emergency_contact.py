from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_alter_clinic_contact_number_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="emergency_contact",
            field=models.CharField(
                max_length=10,
                null=True,
                blank=True,
            ),
        ),
    ]