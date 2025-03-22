from odoo import models, fields, api
from datetime import datetime
import base64
import io
import xlsxwriter

class TaxIvaReportWizard(models.TransientModel):
    _name = 'tax.iva.report.wizard'
    _description = 'Generar Reporte IVA'
    
    date_from = fields.Date(string='Fecha Inicial', required=True)
    date_to = fields.Date(string='Fecha Final', required=True)
    
    def _process_data_for_report(self):
        """
        Prepara los datos para cualquier tipo de reporte (XLSX, PDF, HTML)
        """
        data = self._get_report_data()
        
        # Procesar todos los conceptos juntos (igual que en action_export_xlsx)
        all_concepts = []
        
        # Combinar conceptos de ambas columnas
        for item in data.get('left_column', []) + data.get('right_column', []):
            concept = item.get('concept')
            if not concept:
                continue
                
            code = concept.code if hasattr(concept, 'code') else concept.get('code', '')
            description = concept.description if hasattr(concept, 'description') else concept.get('description', '')
            value_type = concept.value_type if hasattr(concept, 'value_type') else concept.get('value_type', '')
            
            # Verificar si tiene impuestos
            if hasattr(concept, 'tax_ids'):
                has_tax_ids = bool(concept.tax_ids)
            else:
                has_tax_ids = concept.get('tax_ids', False)
            
            value = item.get('value', 0)
            
            # Aplicar regla especial para ciertos conceptos
            if code in ['82', '83', '86', '88', '89'] and value < 0:
                value = 0
            
            # Si el concepto no ha sido configurado
            is_null = False
            if value_type != 'calculated' and not has_tax_ids:
                is_null = True
            
            all_concepts.append({
                'code': code,
                'description': description,
                'value': value,
                'is_null': is_null,
                'concept_text': f"{code} {description}"
            })
        
        # Ordenar todos los conceptos por código
        all_concepts.sort(key=lambda x: x['code'])
        
        # Calcular total
        total_value = sum(concept['value'] for concept in all_concepts if not concept['is_null'])
        
        return {
            'concepts': all_concepts,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company': self.env.company,
            'date': fields.Datetime.now(),
            'user': self.env.user,
            'total': total_value
        }
    
    def _get_report_data(self):
        """
        Obtener datos para el reporte
        """
        concepts = self.env['tax.iva.concept'].search([
            ('code', '>=', '27'), 
            ('code', '<=', '89')
        ], order='code')
        
        concept_values = {}
        for concept in concepts:
            value = concept.calculate_value(self.date_from, self.date_to)
            concept_values[concept.code] = value
            
        # Organizar conceptos en dos columnas
        left_column = []
        right_column = []
        half_length = len(concepts) // 2 + len(concepts) % 2
        
        for i, concept in enumerate(concepts):
            if i < half_length:
                left_column.append({
                    'concept': concept,
                    'value': concept_values.get(concept.code, 0)
                })
            else:
                right_column.append({
                    'concept': concept,
                    'value': concept_values.get(concept.code, 0)
                })
        
        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company': self.env.company,
            'date': fields.Datetime.now(),
            'user': self.env.user,
            'left_column': left_column,
            'right_column': right_column,
        }
    
    def action_view_report(self):
        """
        Ver reporte en pantalla
        """
        report_data = self._process_data_for_report()
        
        # Construir HTML con la misma estructura que el Excel
        html = """
            <style>
                .report-container {
                    width: 100%;
                    font-family: Arial, sans-serif;
                }
                .report-header {
                    margin-bottom: 20px;
                }
                .report-title {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                .report-period {
                    font-size: 13px;
                    margin-bottom: 10px;
                }
                .report-meta div {
                    font-size: 13px;
                    margin-bottom: 3px;
                }
                .report-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }
                .report-table th, .report-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                }
                .report-table th {
                    background-color: #f8f8f8;
                    text-align: left;
                }
                .value-cell {
                    text-align: right;
                }
                .total-row {
                    font-weight: bold;
                }
                .null-value {
                    background-color: #000;
                    color: #000;
                }
            </style>
            
            <div class="report-container">
                <div class="report-header">
                    <div class="report-title">Reporte IVA-300</div>
                    <div class="report-period">{date_from} - {date_to}</div>
                    <div class="report-meta">
                        <div><strong>Empresa:</strong> {company}</div>
                        <div><strong>Fecha Generación:</strong> {date}</div>
                        <div><strong>Usuario:</strong> {user}</div>
                    </div>
                </div>
                
                <table class="report-table">
                    <thead>
                        <tr>
                            <th>Conceptos</th>
                            <th style="width: 150px;">Valor</th>
                        </tr>
                    </thead>
                    <tbody>
        """.format(
            date_from=report_data['date_from'].strftime('%d-%m-%Y'),
            date_to=report_data['date_to'].strftime('%d-%m-%Y'),
            company=report_data['company'].name,
            date=report_data['date'].strftime('%d-%m-%Y %H:%M:%S'),
            user=report_data['user'].name
        )
        
        # Agregar filas para cada concepto
        for concept in report_data['concepts']:
            if concept['is_null']:
                value_html = '<span class="null-value">_</span>'
                value_class = 'null-value'
            else:
                value_html = '{:,.0f}'.format(concept['value'])
                value_class = ''
            
            html += """
                <tr>
                    <td>{concept_text}</td>
                    <td class="value-cell {value_class}">{value}</td>
                </tr>
            """.format(
                concept_text=concept['concept_text'],
                value=value_html,
                value_class=value_class
            )
        
        # Agregar fila de total
        html += """
                    <tr class="total-row">
                        <td>TOTAL</td>
                        <td class="value-cell">{total}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """.format(total='{:,.0f}'.format(report_data['total']))
        
        # Crear y retornar vista
        return {
            'name': 'Reporte IVA',
            'type': 'ir.actions.act_window',
            'res_model': 'tax.iva.report.view',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_date_from': self.date_from,
                'default_date_to': self.date_to,
                'default_html_report': html,
            }
        }
    
    def action_print_report(self):
        """
        Imprimir reporte en PDF usando un método alternativo mientras se resuelve el problema de carga de archivos
        """
        # Procesar datos igual que antes
        report_data = self._process_data_for_report()
        
        # Construir HTML similar al que usamos para la vista
        html_content = """
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .report-table {{ width: 100%; border-collapse: collapse; }}
                .report-table th, .report-table td {{ border: 1px solid #ddd; padding: 8px; }}
                .report-table th {{ background-color: #f8f8f8; }}
                .value-cell {{ text-align: right; }}
                .total-row {{ font-weight: bold; }}
            </style>
            
            <h2 style="text-align: center;">Reporte IVA-300</h2>
            <p style="text-align: center;">{date_from} - {date_to}</p>
            
            <div style="margin-bottom: 15px;">
                <div><strong>Empresa:</strong> {company}</div>
                <div><strong>Fecha Generación:</strong> {date}</div>
                <div><strong>Usuario:</strong> {user}</div>
            </div>
            
            <table class="report-table">
                <thead>
                    <tr>
                        <th>Conceptos</th>
                        <th style="width: 150px;">Valor</th>
                    </tr>
                </thead>
                <tbody>
        """.format(
            date_from=report_data['date_from'].strftime('%d-%m-%Y'),
            date_to=report_data['date_to'].strftime('%d-%m-%Y'),
            company=report_data['company'].name,
            date=report_data['date'].strftime('%d-%m-%Y %H:%M:%S'),
            user=report_data['user'].name
        )
        
        # Agregar filas para cada concepto
        for concept in report_data['concepts']:
            if concept['is_null']:
                value_html = '<span style="color: white; background-color: black;">_</span>'
            else:
                value_html = '{:,.0f}'.format(concept['value'])
            
            html_content += """
                <tr>
                    <td>{concept_text}</td>
                    <td class="value-cell">{value}</td>
                </tr>
            """.format(
                concept_text=concept['concept_text'],
                value=value_html
            )
        
        # Agregar fila de total
        html_content += """
                <tr class="total-row">
                    <td>TOTAL</td>
                    <td class="value-cell">{total}</td>
                </tr>
            </tbody>
        </table>
        """.format(total='{:,.0f}'.format(report_data['total']))
        
        # Crear un adjunto HTML y convertirlo a PDF
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte_IVA_300_{report_data["date_from"].strftime("%Y%m%d")}_al_{report_data["date_to"].strftime("%Y%m%d")}.html',
            'datas': base64.b64encode(html_content.encode('utf-8')),
            'type': 'binary',
            'mimetype': 'text/html',
        })
        
        # Redirigir a descarga (el navegador renderizará el HTML y permitirá imprimirlo como PDF)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    def action_export_xlsx(self):
        """
        Exportar reporte a XLSX
        """
        data = self._get_report_data()
        
        # Crear archivo XLSX
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Reporte IVA-300')
        
        # Estilos
        title_format = workbook.add_format({
            'bold': True, 
            'align': 'center', 
            'valign': 'vcenter',
            'font_size': 16,
            'font_name': 'Arial',
        })
        header_format = workbook.add_format({
            'bold': True, 
            'align': 'center', 
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D3D3D3',
            'font_name': 'Arial',
            'font_size': 11,
        })
        data_format = workbook.add_format({
            'align': 'right',
            'border': 1,
            'num_format': '#,##0',
            'font_name': 'Arial',
            'font_size': 10,
        })
        label_format = workbook.add_format({
            'align': 'left',
            'border': 1,
            'font_name': 'Arial',
            'font_size': 10,
        })
        code_format = workbook.add_format({
            'align': 'center',
            'border': 1,
            'font_name': 'Arial',
            'font_size': 10,
        })
        date_format = workbook.add_format({
            'align': 'left',
            'border': 0,
            'font_name': 'Arial',
            'font_size': 10,
            'num_format': 'dd/mm/yyyy',
        })
        null_format = workbook.add_format({
            'bg_color': '#000000',
            'border': 1,
        })
        
        # Ancho de columnas
        worksheet.set_column('A:A', 8)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 8)
        worksheet.set_column('E:E', 40)
        worksheet.set_column('F:F', 15)
        
        # Título y encabezados
        worksheet.merge_range('A1:F1', 'REPORTE IVA-300', title_format)
        worksheet.write('A2', 'Empresa:', date_format)
        worksheet.merge_range('B2:C2', data['company'].name, date_format)
        worksheet.write('D2', 'Fecha:', date_format)
        worksheet.merge_range('E2:F2', datetime.now().strftime('%d/%m/%Y %H:%M:%S'), date_format)
        worksheet.write('A3', 'Período:', date_format)
        worksheet.merge_range('B3:C3', f"{data['date_from'].strftime('%d/%m/%Y')} - {data['date_to'].strftime('%d/%m/%Y')}", date_format)
        worksheet.write('D3', 'Usuario:', date_format)
        worksheet.merge_range('E3:F3', data['user'].name, date_format)
        
        # Encabezados de tabla
        row = 5
        worksheet.write(row, 0, 'Código', header_format)
        worksheet.write(row, 1, 'Descripción', header_format)
        worksheet.write(row, 2, 'Valor', header_format)
        worksheet.write(row, 3, 'Código', header_format)
        worksheet.write(row, 4, 'Descripción', header_format)
        worksheet.write(row, 5, 'Valor', header_format)
        
        # Ajustar el ancho de las filas
        worksheet.set_row(row, 30)
        
        row += 1
        max_rows = max(len(data['left_column']), len(data['right_column']))
        
        # Datos
        for i in range(max_rows):
            # Columna izquierda
            if i < len(data['left_column']):
                item = data['left_column'][i]
                concept = item['concept']
                value = item['value']
                
                worksheet.write(row, 0, concept.code, code_format)
                worksheet.write(row, 1, concept.description, label_format)
                
                # Aplicar regla especial para ciertos conceptos
                if concept.code in ['82', '83', '86', '88', '89'] and value < 0:
                    value = 0
                
                # Si el concepto no ha sido configurado
                if not concept.tax_ids and concept.value_type != 'calculated':
                    worksheet.write(row, 2, '', null_format)
                else:
                    worksheet.write(row, 2, value, data_format)
            else:
                # Celdas vacías
                worksheet.write(row, 0, '', label_format)
                worksheet.write(row, 1, '', label_format)
                worksheet.write(row, 2, '', label_format)
            
            # Columna derecha
            if i < len(data['right_column']):
                item = data['right_column'][i]
                concept = item['concept']
                value = item['value']
                
                worksheet.write(row, 3, concept.code, code_format)
                worksheet.write(row, 4, concept.description, label_format)
                
                # Aplicar regla especial para ciertos conceptos
                if concept.code in ['82', '83', '86', '88', '89'] and value < 0:
                    value = 0
                
                # Si el concepto no ha sido configurado
                if not concept.tax_ids and concept.value_type != 'calculated':
                    worksheet.write(row, 5, '', null_format)
                else:
                    worksheet.write(row, 5, value, data_format)
            else:
                # Celdas vacías
                worksheet.write(row, 3, '', label_format)
                worksheet.write(row, 4, '', label_format)
                worksheet.write(row, 5, '', label_format)
                
            row += 1
        
        workbook.close()
        
        # Crear adjunto para descargar
        output.seek(0)
        xlsx_data = output.read()
        
        attachment = self.env['ir.attachment'].create({
            'name': f'Reporte_IVA_300_{data["date_from"].strftime("%Y%m%d")}_al_{data["date_to"].strftime("%Y%m%d")}.xlsx',
            'datas': base64.b64encode(xlsx_data),
            'type': 'binary',
        })
        
        # Redirigir a descarga
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=ir.attachment&id={}&filename={}&field=datas'.format(
                attachment.id, attachment.name),
            'target': 'self',
        }


class TaxIvaReportView(models.TransientModel):
    _name = 'tax.iva.report.view'
    _description = 'Vista del Reporte IVA'
    
    date_from = fields.Date(string='Fecha Inicial', readonly=True)
    date_to = fields.Date(string='Fecha Final', readonly=True)
    html_report = fields.Html(string='Reporte', readonly=True)