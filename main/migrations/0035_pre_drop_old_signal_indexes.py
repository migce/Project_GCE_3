from django.db import migrations


class Migration(migrations.Migration):

    # Make sure this runs before the auto-generated 0035 that removes old indexes
    run_before = [
        ('main', '0035_remove_signalevent_main_signal_system__7b2c63_idx_and_more'),
    ]

    dependencies = [
        ('main', '0034_marketbar_created_at'),
    ]

    operations = [
        migrations.RunSQL('DROP INDEX IF EXISTS "main_signal_bar_direc_3d9265_idx";', reverse_sql=''),
        migrations.RunSQL('DROP INDEX IF EXISTS "main_signal_trading_7df8e2_idx";', reverse_sql=''),
        migrations.RunSQL('DROP INDEX IF EXISTS "main_signal_timefra_0a6f37_idx";', reverse_sql=''),
    ]

