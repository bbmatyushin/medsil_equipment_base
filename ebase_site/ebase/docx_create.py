"""Создание документом для инженеров - актов"""

import os
from pathlib import Path

from django.conf import settings
from docx import Document
from docx.table import Table
from docx.oxml.shared import OxmlElement
from docx.oxml.ns import qn

class CreateServiceAkt:
    TEMPLATE_PATH = str(Path(settings.MEDIA_ROOT, 'docs', 'service_akt', 'service_akt_MEDSIL.docx'))  # путь к шаблону

    def __init__(self, client: dict, job_content: str,
                 description: str, spare_parts: list):
        self.akt = Document(self.TEMPLATE_PATH)
        self.client = client
        self.description = description
        self.job_content = job_content
        self.spare_parts = spare_parts
        self.save_file_path = self.create_save_path()

    def create_save_path(self) -> str:
        """Проверяет наличие папки для хранения актов определенной модели оборудования"""
        equipment_short_name = self.client['equipment_short_name'] \
            .replace(' ', '_') \
            .replace('/', '-')
        eq_dir_path = Path(settings.MEDIA_ROOT, 'docs', 'service_akt', equipment_short_name)
        file_name = (f"service_akt_MEDSIL_{self.client['{{ SERIAL_NUM }}'].replace(' ', '_')}"
                     f"{'_' + self.client['{{ DATE }}'] if not self.client['{{ DATE }}'].startswith('___') else ''}"
                     f".docx")
        if not os.path.exists(eq_dir_path):
            os.mkdir(eq_dir_path)

        return str(Path(settings.MEDIA_ROOT, 'docs', 'service_akt',
                        equipment_short_name, file_name))

    def update_paragraphs(self):
        """Для обновления абзацев. НЕ ИСПОЛЬЗУЕТСЯ"""
        for par in self.akt.paragraphs:
            if 'PART_SERV' in par.text:
                par.text = par.text.replace('PART_SERV', 'NEW DETAIL')

    def update_tables(self):
        """Обноления данных в таблицах документа WORD"""
        for i, table in enumerate(self.akt.tables, start=1):
            if i == 1: self.main_table(table)
            if i == 2: self.description_update(table)
            if i == 3: self.job_content_update(table)
            if i == 4 and len(self.spare_parts) > 0: self.spare_part_table(table)  # Используемые запчасти

        self.akt.save(self.save_file_path)

    @staticmethod
    def cell_paragraph_gen(table: Table):
        """Возвращает абзац из ячейки таблицы"""
        for n, row in enumerate(table.rows, start=1):
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield n, paragraph

    def main_table(self, table: Table):
        """Обновления даттых в таблице с реквизитами"""
        for n, paragraph in self.cell_paragraph_gen(table):
            for k, v in self.client.items():
                if k in paragraph.text:
                    paragraph.text = paragraph.text.replace(k, v)
                    if k == '{{ CLIENT }}':
                        paragraph.runs[0].bold = True

    def description_update(self, table: Table):
        """Обновление описания работ"""
        for n, paragraph in self.cell_paragraph_gen(table):
            if n == 4:
                paragraph.text = self.description

    def job_content_update(self, table):
        """Описание проведенных работ"""
        for n, paragraph in self.cell_paragraph_gen(table):
            if n == 1:
                paragraph.text = self.job_content


    def spare_part_table(self, table: Table):
        """Обновляем данные в таблице Замененные детали"""
        count_parts = len(self.spare_parts)
        for n, paragraph in self.cell_paragraph_gen(table):
            paragraph.text = f"{n}. {self.spare_parts[n - 1][0]} (арт. {self.spare_parts[n - 1][1]})"
        if len(table.rows) < count_parts:
            for i in range(count_parts - len(table.rows)):
                cell = table.add_row().cells[0]
                cell_tcPr = cell._tc.tcPr

                # рисуем границы для ячейки
                tc_border = OxmlElement('w:tcBorders')
                top = OxmlElement('w:top')
                bottom = OxmlElement('w:bottom')
                left = OxmlElement('w:left')
                right = OxmlElement('w:right')

                borders = [top, right, bottom, left]

                for b in borders:
                    b.set(qn('w:val'), 'single')
                    b.set(qn('w:sz'), '4')
                    b.set(qn('w:space'), '0')
                    b.set(qn('w:color'), '000000')
                    tc_border.append(b)

                cell_tcPr.append(tc_border)
                cell.text = (f"{len(table.rows)}. "
                             f"{self.spare_parts[len(table.rows) - 1][0]} "
                             f"(арт. {self.spare_parts[len(table.rows) - 1][1]})")


if __name__ == '__main__':
    CreateServiceAkt(client={}).update_tables()
