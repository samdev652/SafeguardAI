from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0004_communityverificationprompt'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='communityverificationprompt',
            new_name='alerts_comm_phone_n_5f83f6_idx',
            old_name='alerts_comm_phone_n_3f4380_idx',
        ),
        migrations.RenameIndex(
            model_name='incidentreport',
            new_name='alerts_inci_county__b55558_idx',
            old_name='alerts_inci_county__4a2a29_idx',
        ),
    ]
