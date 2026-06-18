# Generated manually to change SparePartShipmentM2M.quantity
# from integer to double precision (float).
# Note: model not registered in prior migrations, so using raw SQL.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("spare_part", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE "medsil"."spare_part_shipment_m2m" ALTER COLUMN "quantity" TYPE double precision;',
            reverse_sql='ALTER TABLE "medsil"."spare_part_shipment_m2m" ALTER COLUMN "quantity" TYPE integer USING "quantity"::integer;',
        ),
    ]
