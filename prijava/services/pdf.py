import io
import os
from datetime import datetime

from flask import current_app
from fpdf import FPDF


class ApplicationsPDF(FPDF):
    """Unified PDF generator for the admin application exports."""

    col_width_1 = 50   # Ime i prezime deteta
    col_width_2 = 20   # Razred
    col_width_3 = 90   # Roditelji
    col_width_4 = 30   # Datum prijave

    def __init__(
        self,
        *,
        title,
        filters,
        show_school_name=False,
        title_size=15,
        body_size=10,
        row_height=10,
        filter_date_format='%d.%m.%Y.',
        header_fill_rgb=None,
    ):
        super().__init__()
        font_path = os.path.join(current_app.root_path, 'static', 'fonts')
        self.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
        self.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)

        self._title_text = title
        self._filters = filters
        self._show_school_name = show_school_name
        self._title_size = title_size
        self._body_size = body_size
        self._row_height = row_height
        self._filter_date_format = filter_date_format
        self._header_fill_rgb = header_fill_rgb

    def header(self):
        if self._show_school_name:
            school_name = os.getenv('SCHOOL_NAME')
            if school_name:
                self.set_font('DejaVu', 'B', 14)
                self.cell(0, 10, school_name, 0, new_x="LMARGIN", new_y="NEXT", align='C')

            self.set_font('DejaVu', 'B', self._title_size)
            self.cell(0, 10, self._title_text, 0, new_x="LMARGIN", new_y="NEXT", align='C')

            self._render_filter_line()

            self.set_font('DejaVu', '', 8)
            self.cell(0, 5, f'Generisano: {datetime.now().strftime("%d.%m.%Y. %H:%M")}',
                      0, new_x="LMARGIN", new_y="NEXT", align='R')
            self.ln(5)
        else:
            self.set_font('DejaVu', 'B', self._title_size)
            self.cell(0, 10, self._title_text, 0, new_x="LMARGIN", new_y="NEXT", align='C')

            self.set_font('DejaVu', '', 10)
            self.cell(0, 10, f'Generisano: {datetime.now().strftime("%d.%m.%Y. %H:%M")}',
                      0, new_x="LMARGIN", new_y="NEXT", align='R')

            self._render_filter_line()

        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.set_y(self.get_y() + 5)

        self.set_font('DejaVu', 'B', 11)
        fill = self._header_fill_rgb is not None
        if fill:
            self.set_fill_color(*self._header_fill_rgb)

        self.cell(self.col_width_1, 10, 'Ime i prezime deteta', 1, align='C', fill=fill)
        self.cell(self.col_width_2, 10, 'Razred', 1, align='C', fill=fill)
        self.cell(self.col_width_3, 10, 'Roditelji', 1, align='C', fill=fill)
        self.cell(self.col_width_4, 10, 'Datum prijave', 1, new_x="LMARGIN", new_y="NEXT", align='C', fill=fill)

    def _render_filter_line(self):
        if not self._filters:
            return

        parts = []
        search = self._filters.get('search')
        date_from = self._filters.get('date_from')
        date_to = self._filters.get('date_to')
        grade = self._filters.get('grade')

        if search:
            parts.append(f"Pretraga: '{search}'")
        if date_from:
            formatted = date_from.strftime(self._filter_date_format) if isinstance(date_from, datetime) else date_from
            parts.append(f"Od datuma: {formatted}")
        if date_to:
            formatted = date_to.strftime(self._filter_date_format) if isinstance(date_to, datetime) else date_to
            parts.append(f"Do datuma: {formatted}")
        if grade:
            parts.append(f"Razred: {grade}")

        if not parts:
            return

        self.set_font('DejaVu', '', 10)
        self.cell(0, 10, "Primenjeni filteri: " + ", ".join(parts),
                  0, new_x="LMARGIN", new_y="NEXT", align='L')

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Strana {self.page_no()}/{{nb}}',
                  0, new_x="LMARGIN", new_y="NEXT", align='C')

    def render_rows(self, applications):
        self.set_font('DejaVu', '', self._body_size)
        h = self._row_height
        for application in applications:
            if self.get_y() > self.h - 30:
                self.add_page()

            self.cell(self.col_width_1, h,
                      f"{application.children_name} {application.children_surname}", 1, align='L')
            self.cell(self.col_width_2, h,
                      f"{application.grade}/{application.class_number}", 1, align='C')
            parent_info = (f"M: {application.mother_name} {application.mother_surname}, "
                           f"O: {application.father_name} {application.father_surname}")
            self.cell(self.col_width_3, h, parent_info, 1, align='L')
            self.cell(self.col_width_4, h,
                      application.date_submitted.strftime('%d.%m.%Y. %H:%M'),
                      1, new_x="LMARGIN", new_y="NEXT", align='C')

    def render_total(self, count):
        self.set_font('DejaVu', 'B', 11)
        total_width = self.col_width_1 + self.col_width_2 + self.col_width_3 + self.col_width_4
        self.cell(total_width, 10, f"Ukupan broj prijava: {count}",
                  0, new_x="LMARGIN", new_y="NEXT", align='R')


def render_applications_pdf(
    applications,
    filters,
    *,
    title,
    show_school_name=False,
    title_size=15,
    body_size=10,
    row_height=10,
    filter_date_format='%d.%m.%Y.',
    header_fill_rgb=None,
    show_total=True,
):
    """Render the applications export PDF and return the raw bytes."""
    pdf = ApplicationsPDF(
        title=title,
        filters=filters,
        show_school_name=show_school_name,
        title_size=title_size,
        body_size=body_size,
        row_height=row_height,
        filter_date_format=filter_date_format,
        header_fill_rgb=header_fill_rgb,
    )
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.render_rows(applications)
    if show_total:
        pdf.render_total(len(applications))

    output = io.BytesIO()
    pdf.output(output)
    return output.getvalue()
