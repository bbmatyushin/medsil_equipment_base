from django.contrib import admin
from utils.export_to_xlsx import export_to_excel_formatted

class MainModelAdmin(admin.ModelAdmin):
    list_per_page = 20
    actions = [export_to_excel_formatted]