# Generated manually — adds missing returned_to_office column to service table
# Uses DO block to safely add column only if it doesn't exist yet

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ebase', '0008_remove_moved_models'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'medsil'
                          AND table_name = 'service'
                          AND column_name = 'returned_to_office'
                    ) THEN
                        ALTER TABLE "medsil"."service"
                        ADD COLUMN "returned_to_office" boolean DEFAULT false NOT NULL;
                    END IF;
                END $$;
            """,
            reverse_sql="""ALTER TABLE "medsil"."service" DROP COLUMN IF EXISTS "returned_to_office";""",
        ),
    ]
