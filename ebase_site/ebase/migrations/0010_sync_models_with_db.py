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
        ("spare_part", "0005_sync_models_with_db"),
        ("ebase", "0009_add_returned_to_office"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                                                                migrations.CreateModel(
                                                                    name='ReplacementEquipment',
                                                                    fields=[
                                                                        ('id', models.UUIDField(db_comment='ID записи', default=uuid.uuid4, editable=False, help_text='ID записи', primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True, db_comment='Дата создания записи.', help_text='Дата создания записи. Заполняется автоматически', verbose_name='Дата создания')),
                                                                        ('serial_number', models.CharField(db_comment='Серийный номер подменного прибора', help_text='Серийный номер подменного прибора', max_length=50, verbose_name='Серийный номер')),
                                                                        ('state', models.CharField(choices=[('working', 'Рабочий'), ('not_working', 'Не рабочий')], db_comment='Состояние оборудования: рабочий/не рабочий', default='working', help_text='Состояние оборудования', max_length=20, verbose_name='Состояние')),
                                                                        ('comment', models.TextField(blank=True, db_comment='Комментарий к подменному оборудованию', null=True, verbose_name='Комментарий')),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Подменное оборудование',
                                                                        'verbose_name_plural': 'Подменное оборудование',
                                                                        'db_table': '"medsil"."replacement_equipment"',
                                                                        'db_table_comment': 'Подменное оборудование для временной замены.\n\n-- BMatyushin',
                                                                    },
                                                                ),
                                                                migrations.CreateModel(
                                                                    name='ServiceAccessories',
                                                                    fields=[
                                                                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                                                        ('quantity', models.PositiveIntegerField(db_comment='Количество комплектующих', default=1, help_text='Количество используемых комплектующих', verbose_name='Количество')),
                                                                        ('create_dt', models.DateTimeField(auto_now_add=True, db_comment='Дата создания записи', verbose_name='Дата создания')),
                                                                    ],
                                                                    options={
                                                                        'verbose_name': 'Комплектующее для ремонта',
                                                                        'verbose_name_plural': 'Комплектующие для ремонта',
                                                                        'db_table': '"medsil"."service_accessories"',
                                                                        'db_table_comment': 'Связь ремонта с комплектующими и их количеством.\n\n-- BMatyushin',
                                                                    },
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='equipmentaccounting',
                                                                    name='comment',
                                                                    field=models.TextField(blank=True, db_comment='Комментарий', null=True, verbose_name='Комментарий'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='equipmentaccounting',
                                                                    name='is_our_reagents',
                                                                    field=models.BooleanField(db_comment='True, если реагенты поставляются нами', default=False, verbose_name='Поставка реагентов'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='accept_from_akt',
                                                                    field=models.CharField(blank=True, db_comment='Акт приема-передачи оборудования из ремонт', help_text='Акт приёма-передачи оборудования из ремонт', max_length=2056, null=True, validators=[django.core.validators.RegexValidator(regex='\\.docs$|\\.doc$')], verbose_name='Акт из ремонта'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='accept_in_akt',
                                                                    field=models.CharField(blank=True, db_comment='Акт приема-передачи оборудования в ремонт', help_text='Акт приёма-передачи оборудования в ремонт', max_length=2056, null=True, validators=[django.core.validators.RegexValidator(regex='\\.docs$|\\.doc$')], verbose_name='Акт в ремонт'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='contact_person_data',
                                                                    field=models.JSONField(blank=True, db_comment='Для хранения данных выбранного контактного лица. Формат - {contact_person_id: id, fio: "ФИО"}', default=dict, editable=False),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='returned_to_office',
                                                                    field=models.BooleanField(db_comment='Флаг, означающий что подменное оборудование физически вернулось в офис', default=False, help_text='Отметьте, если подменное оборудование фактически вернулось в офис', verbose_name='Вернули в офис'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='service_akt',
                                                                    field=models.CharField(blank=True, db_comment='Акт о проведении работ', help_text='Акт о проведении работ', max_length=2056, null=True, validators=[django.core.validators.RegexValidator(regex='\\.docs$|\\.doc$')], verbose_name='Акт'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='spare_part_count',
                                                                    field=models.JSONField(blank=True, db_comment='Для хранения сколько и каких запчестей использовалось в ремонте. Формат - {spare_part_id: {expiration_dt: date, service_part_count: count}}', default=dict, editable=False),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='servicephotos',
                                                                    name='user',
                                                                    field=models.ForeignKey(blank=True, db_comment='ID Пользователя (сотрудника)', help_text='Пользователь из таблицы "Пользователи"', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='service_photo_user', to=settings.AUTH_USER_MODEL, verbose_name='ID Пользователя'),
                                                                ),
                                                                migrations.AlterField(
                                                                    model_name='equipmentaccounting',
                                                                    name='is_our_service',
                                                                    field=models.BooleanField(db_comment='True, если оборудование обслуживалось нами', default=False, verbose_name='Проведено ТО'),
                                                                ),
                                                                migrations.AlterField(
                                                                    model_name='servicephotos',
                                                                    name='create_dt',
                                                                    field=models.DateTimeField(auto_now_add=True, verbose_name='Когда было добавлено фото'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipment',
                                                                    index=models.Index(fields=['full_name'], name='equipment_full_na_8dd265_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipment',
                                                                    index=models.Index(fields=['short_name'], name='equipment_short_n_d1fa1f_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipment',
                                                                    index=models.Index(fields=['med_direction'], name='equipment_med_dir_efc333_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipment',
                                                                    index=models.Index(fields=['manufacturer'], name='equipment_manufac_87cc5e_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipment',
                                                                    index=models.Index(fields=['supplier'], name='equipment_supplie_4101ee_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccdepartment',
                                                                    index=models.Index(fields=['equipment_accounting'], name='equipment_a_equipme_bcdebf_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccdepartment',
                                                                    index=models.Index(fields=['department'], name='equipment_a_departm_1f190e_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccdepartment',
                                                                    index=models.Index(fields=['is_active'], name='equipment_a_is_acti_05d814_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccdepartment',
                                                                    index=models.Index(fields=['install_dt'], name='equipment_a_install_a080e2_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccdepartment',
                                                                    index=models.Index(fields=['engineer'], name='equipment_a_enginee_86ea65_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccounting',
                                                                    index=models.Index(fields=['equipment'], name='equipment_a_equipme_c618f1_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccounting',
                                                                    index=models.Index(fields=['equipment_status'], name='equipment_a_equipme_ea57b6_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccounting',
                                                                    index=models.Index(fields=['is_our_supply'], name='equipment_a_is_our__cead3b_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccounting',
                                                                    index=models.Index(fields=['is_our_service'], name='equipment_a_is_our__5b65f6_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='equipmentaccounting',
                                                                    index=models.Index(fields=['user'], name='equipment_a_user_id_35a026_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['equipment_accounting'], name='service_equipme_0272e4_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['service_type'], name='service_service_9f47bf_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['beg_dt'], name='service_beg_dt_42470c_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['end_dt'], name='service_end_dt_5b40b7_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['-beg_dt'], name='service_beg_dt_f03af3_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='service',
                                                                    index=models.Index(fields=['user'], name='service_user_id_0f8985_idx'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='serviceaccessories',
                                                                    name='accessory',
                                                                    field=models.ForeignKey(db_comment='ID комплектующего', on_delete=django.db.models.deletion.CASCADE, related_name='service_accessories_accessory', to='spare_part.sparepartaccessories', verbose_name='Комплектующее'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='serviceaccessories',
                                                                    name='service',
                                                                    field=models.ForeignKey(db_comment='ID ремонта', on_delete=django.db.models.deletion.CASCADE, related_name='service_accessories', to='ebase.service', verbose_name='Ремонт'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='replacementequipment',
                                                                    name='accessories',
                                                                    field=models.ManyToManyField(blank=True, db_comment='ID комплектующих к прибору', help_text='Комплектующие, которые передаются с прибором', related_name='replacement_equipment_accessories', to='spare_part.sparepartaccessories', verbose_name='Комплектующие'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='replacementequipment',
                                                                    name='equipment',
                                                                    field=models.ForeignKey(db_comment='ID модели подменного оборудования', help_text='Модель подменного оборудования', on_delete=django.db.models.deletion.RESTRICT, related_name='replacement_equipment_equipment', to='ebase.equipment', verbose_name='Модель оборудования'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='replacementequipment',
                                                                    name='user',
                                                                    field=models.ForeignKey(db_comment='Пользователь, который добавил запись о подменном оборудовании', help_text='Пользователь, который добавил запись о подменном оборудовании', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replacement_equipment_user', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='accessories',
                                                                    field=models.ManyToManyField(blank=True, help_text='Комплектующие, используемые в ремонте', through='ebase.ServiceAccessories', to='spare_part.sparepartaccessories', verbose_name='Комплектующие'),
                                                                ),
                                                                migrations.AddField(
                                                                    model_name='service',
                                                                    name='replacement_equipment',
                                                                    field=models.OneToOneField(blank=True, db_comment='ID подменного оборудования, передаваемого на время ремонта', help_text='Подменное оборудование, передаваемое на время ремонта', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_replacement_equipment', to='ebase.replacementequipment', verbose_name='Передается на время ремонта'),
                                                                ),
                                                                migrations.AlterUniqueTogether(
                                                                    name='serviceaccessories',
                                                                    unique_together={('service', 'accessory')},
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='replacementequipment',
                                                                    index=models.Index(fields=['equipment'], name='replacement_equipme_715171_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='replacementequipment',
                                                                    index=models.Index(fields=['serial_number'], name='replacement_serial__aad802_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='replacementequipment',
                                                                    index=models.Index(fields=['state'], name='replacement_state_c3efff_idx'),
                                                                ),
                                                                migrations.AddIndex(
                                                                    model_name='replacementequipment',
                                                                    index=models.Index(fields=['user'], name='replacement_user_id_185f59_idx'),
                                                                ),
            ],
            database_operations=[],
        )
    ]
