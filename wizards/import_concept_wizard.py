from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import logging
import tempfile
import os

_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot import xlrd')

class ImportConceptWizard(models.TransientModel):
    _name = 'import.concept.wizard'
    _description = 'Importar Conceptos desde Excel'

    excel_file = fields.Binary(string='Archivo Excel', required=True)
    file_name = fields.Char(string='Nombre del archivo')
    
    def _parse_excel_file(self):
        """
        Parsea el archivo Excel y retorna los datos
        """
        if not self.excel_file:
            raise UserError(_('Por favor, seleccione un archivo Excel.'))
            
        try:
            # Guardar archivo en disco temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp:
                temp.write(base64.b64decode(self.excel_file))
                temp_path = temp.name
            
            # Leer archivo Excel
            book = xlrd.open_workbook(temp_path)
            sheet = book.sheet_by_index(0)
            
            # Eliminar archivo temporal
            os.unlink(temp_path)
            
            # Extraer datos
            headers = [cell.value for cell in sheet.row(0)]
            data = []
            
            for row_idx in range(1, sheet.nrows):
                row_dict = {}
                for col_idx, header in enumerate(headers):
                    cell_value = sheet.cell(row_idx, col_idx).value
                    row_dict[header] = cell_value
                data.append(row_dict)
                
            return data
        except Exception as e:
            raise UserError(_('Error al procesar el archivo Excel: %s') % str(e))
    
    def action_import_concepts(self):
        """
        Importa los conceptos desde el archivo Excel
        """
        data = self._parse_excel_file()
        
        if not data:
            raise UserError(_('No se encontraron datos en el archivo Excel.'))
            
        concept_obj = self.env['tax.iva.concept']
        tax_obj = self.env['account.tax']
        
        # Mapeo de columnas esperadas en el Excel
        # Ajustar estos nombres según la estructura real de tu Excel
        code_field = 'Código'
        desc_field = 'Descripción'
        op_type_field = 'Tipo de Operación'
        value_type_field = 'Tipo de Valor'
        taxes_field = 'Impuestos'
        formula_field = 'Fórmula de Cálculo'
        
        imported_count = 0
        errors = []
        
        for row in data:
            # Verificar campos requeridos
            if not row.get(code_field) or not row.get(desc_field) or not row.get(op_type_field) or not row.get(value_type_field):
                errors.append(_('Fila con datos incompletos: %s') % str(row))
                continue
                
            # Convertir tipos de operación
            op_type = row.get(op_type_field).lower()
            if op_type == 'ventas':
                op_type = 'sale'
            elif op_type == 'compras':
                op_type = 'purchase'
            else:
                errors.append(_('Tipo de operación no válido (%s): %s') % (op_type, str(row)))
                continue
                
            # Convertir tipos de valor
            value_type = row.get(value_type_field).lower()
            if value_type == 'base':
                value_type = 'base'
            elif value_type == 'impuesto':
                value_type = 'tax'
            elif value_type == 'calculado':
                value_type = 'calculated'
            else:
                errors.append(_('Tipo de valor no válido (%s): %s') % (value_type, str(row)))
                continue
                
            # Buscar impuestos si se especifican
            tax_ids = []
            if row.get(taxes_field):
                tax_names = str(row.get(taxes_field)).split(',')
                for tax_name in tax_names:
                    tax_name = tax_name.strip()
                    if tax_name:
                        tax = tax_obj.search([
                            ('name', '=', tax_name),
                            ('type_tax_use', '=', op_type)
                        ], limit=1)
                        
                        if not tax:
                            errors.append(_('Impuesto no encontrado (%s): %s') % (tax_name, str(row)))
                            continue
                            
                        tax_ids.append(tax.id)
            
            # Verificar si el concepto ya existe
            existing = concept_obj.search([('code', '=', str(row.get(code_field)))], limit=1)
            
            try:
                if existing:
                    # Actualizar concepto existente
                    existing.write({
                        'description': str(row.get(desc_field)),
                        'operation_type': op_type,
                        'value_type': value_type,
                        'tax_ids': [(6, 0, tax_ids)],
                        'calculation_formula': row.get(formula_field, False) and str(row.get(formula_field)) or False,
                    })
                else:
                    # Crear nuevo concepto
                    concept_obj.create({
                        'code': str(row.get(code_field)),
                        'description': str(row.get(desc_field)),
                        'operation_type': op_type,
                        'value_type': value_type,
                        'tax_ids': [(6, 0, tax_ids)],
                        'calculation_formula': row.get(formula_field, False) and str(row.get(formula_field)) or False,
                    })
                
                imported_count += 1
            except Exception as e:
                errors.append(_('Error al importar concepto (%s): %s') % (row.get(code_field), str(e)))
        
        # Mostrar resultados
        message = _('Se importaron %s conceptos correctamente.') % imported_count
        
        if errors:
            message += _('\n\nSe encontraron los siguientes errores:')
            for error in errors:
                message += '\n- ' + error
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Importación de Conceptos'),
                'message': message,
                'sticky': True,
                'type': 'info' if not errors else 'warning',
            }
        }