# Sync migration: updates Django state to match production DB.
# These tables/columns already exist in the database from prior
# production migrations that were never committed to git.

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ebase", "0009_add_returned_to_office"),
        ("spare_part", "0004_sparepartsupplyv2_and_items"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                                                                migrations.CreateModel(
                                                                    name='SparePartAccessories',
                                                                    fields=[
                                                                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('name', models.CharField(db_comment='Наименование комплектующих', help_text='Описание комплектующих, которые передаются с подменным оборудованием', max_length=200, verbose_name='Наименование комплектующих')),
                                                                        ('description', models.TextField(blank=True, db_comment='Подробное описание комплектующих', null=True, verbose_name='Описание')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True, db_comment='Дата создания записи.', help_text='Дата создания записи. Заполняется автоматически', verbose_name='Дата создания')),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Комплектующие',
                                                                        'verbose_name_plural': 'Комплектующие',
                                                                        'db_table': '"medsil"."accessories"',
                                                                        'db_table_comment': 'Комплектующие для подменного оборудования.\n\n-- BMatyushin',
                                                                    },
                                                                ),
                                                                migrations.CreateModel(
                                                                    name='SparePartPhoto',
                                                                    fields=[
                                                                        ('id', models.UUIDField(db_comment='ID записи', default=uuid.uuid4, editable=False, help_text='ID записи', primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('photo', models.ImageField(blank=True, db_comment='Ссылка на поле для фото связанных с запчастей', null=True, upload_to='spare_part/%Y/', verbose_name='Фото запчасти')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True, verbose_name='Когда было добавлено фото')),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Фото запчасти',
                                                                        'verbose_name_plural': 'Фото запчастей',
                                                                        'db_table': '"medsil"."spare_part_photo"',
                                                                        'db_table_comment': 'Фотографии запчастей. \n\n-- BMatyushin',
                                                                    },
                                                                ),
                                                                migrations.CreateModel(
                                                                    name='SparePartShipmentM2M',
                                                                    fields=[
                                                                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('quantity', models.FloatField(help_text='Количество отгружаемых единиц товара', validators=[django.core.validators.MinValueValidator(0)], verbose_name='Кол-во')),
                                                                        ('expiration_dt', models.DateField(blank=True, db_comment='Срок годности для запчастей со сроком годности', help_text='Срок годности для запчастей со сроком годности', null=True, verbose_name='Срок годности')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True)),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Выбрать запчасть',
                                                                        'verbose_name_plural': 'Выберите запчасти',
                                                                        'db_table': '"medsil"."spare_part_shipment_m2m"',
                                                                        'db_table_comment': 'Связывает отгрузку, запчать и количество отгруженных запчастей.\r\n\r\n--Матюшин',
                                                                    },
                                                                ),
                                                                migrations.CreateModel(
                                                                    name='SparePartShipmentV2',
                                                                    fields=[
                                                                        ('id', models.UUIDField(db_comment='ID записи', default=uuid.uuid4, editable=False, help_text='ID записи', primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True, db_comment='Дата создания записи.', help_text='Дата создания записи. Заполняется автоматически', verbose_name='Дата создания')),
                                                                        ('doc_num', models.CharField(db_comment='Номер документа отгрузки', default='б/н', help_text='Номер документа отгрузки или внутренний номер для учёта', max_length=20, verbose_name='Номер документа')),
                                                                        ('shipment_dt', models.DateField(db_comment='Дата отгрузки', help_text='Дата отгрузки.', verbose_name='Дата отгрузки')),
                                                                        ('comment', models.TextField(blank=True, db_comment='Комментарий к отгрузке', help_text='Комментарий к отгрузке', null=True, verbose_name='Комментарий')),
                                                                        ('is_auto_comment', models.BooleanField(blank=True, db_comment='true если коммент был создано на стороне django, если пользователем - false', default=False)),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Отгрузка запчастей',
                                                                        'verbose_name_plural': 'Отгрузки запчастей',
                                                                        'db_table': '"medsil"."spare_part_shipment_v2"',
                                                                        'db_table_comment': 'Обновленная таблица для хранения отгрузок запчастей. Для связи одной отгрузки с несколькими запчастями используется таблица spare_part_shipment_m2m, в которй указывается количество отгруженного товара.\r\n\r\n--Матюшин',
                                                                    },
                                                                ),
                                                                migrations.AlterModelOptions(
                                                                    name='sparepartshipment',
                                                                    options={'verbose_name': 'Отгрузка запчастей (до 24.10.2025)', 'verbose_name_plural': 'Отгрузки запчастей (до 24.10.2025)'},
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipment',
                                                                    name='comment',
                                                                    field=models.TextField(blank=True, db_comment='Комментарий к отгрузке', help_text='Комментарий к отгрузке', null=True, verbose_name='Комментарий'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipment',
                                                                    name='is_auto_comment',
                                                                    field=models.BooleanField(blank=True, db_comment='true если коммент был создано на стороне django, если пользователем - false', default=False),
                                                                ),
                                                                migrations.AlterField(
                                                                    model_name='sparepartcount',
                                                                    name='amount',
                                                                    field=models.FloatField(db_comment='Кол-во запчастей', help_text='Кол-во запчастей. Заполняется автоматически', verbose_name='Количество'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepart',
                                                                    index=models.Index(fields=['article'], name='spare_part_article_187345_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepart',
                                                                    index=models.Index(fields=['name'], name='spare_part_name_29d4cd_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepart',
                                                                    index=models.Index(fields=['unit'], name='spare_part_unit_id_22e061_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartcount',
                                                                    index=models.Index(fields=['spare_part'], name='spare_part__spare_p_5cafe6_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartsupply',
                                                                    index=models.Index(fields=['spare_part'], name='spare_part__spare_p_0ac348_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartsupply',
                                                                    index=models.Index(fields=['user'], name='spare_part__user_id_5cd1ee_idx'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipmentv2',
                                                                    name='service',
                                                                    field=models.ForeignKey(blank=True, db_comment='Связь с ремонтом оборудования', help_text='Связь с ремонтом оборудования', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='fk_spare_part_shipment_v2', to='ebase.service', verbose_name='Ремонт оборудования'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipmentv2',
                                                                    name='spare_part',
                                                                    field=models.ManyToManyField(help_text='Для связи одной отгрузки с несколькими запчастями', related_name='m2m_spare_part_shipment_v2', through='spare_part.SparePartShipmentM2M', to='spare_part.sparepart'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipmentv2',
                                                                    name='user',
                                                                    field=models.ForeignKey(db_comment='ID сотрудника, который оформил отгрузку', on_delete=django.db.models.deletion.RESTRICT, related_name='fk_spare_part_shipment_v2_user', to=settings.AUTH_USER_MODEL, verbose_name='Кто отгрузил'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipmentm2m',
                                                                    name='shipment',
                                                                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shipment_m2m', to='spare_part.sparepartshipmentv2'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartshipmentm2m',
                                                                    name='spare_part',
                                                                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='spare_part_m2m', to='spare_part.sparepart', verbose_name='Запчасть'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartphoto',
                                                                    name='spare_part',
                                                                    field=models.ForeignKey(db_comment='ID запчасти', on_delete=django.db.models.deletion.CASCADE, related_name='spare_part_photo', to='spare_part.sparepart', verbose_name='Запчасть'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='sparepartphoto',
                                                                    name='user',
                                                                    field=models.ForeignKey(blank=True, db_comment='ID Пользователя (сотрудника)', help_text='Пользователь из таблицы "Пользователи"', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='spare_part_photo_user', to=settings.AUTH_USER_MODEL, verbose_name='ID Пользователя'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartshipmentv2',
                                                                    index=models.Index(fields=['service'], name='spare_part__service_f4d148_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartshipmentv2',
                                                                    index=models.Index(fields=['user'], name='spare_part__user_id_43e5f5_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartshipmentm2m',
                                                                    index=models.Index(fields=['spare_part'], name='spare_part__spare_p_3294a9_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='sparepartshipmentm2m',
                                                                    index=models.Index(fields=['shipment'], name='spare_part__shipmen_919665_idx'),
                                                                ),
            ],
            database_operations=[],
        )
    ]
