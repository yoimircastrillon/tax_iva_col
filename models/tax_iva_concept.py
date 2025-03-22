from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TaxIvaConcept(models.Model):
    _name = 'tax.iva.concept'
    _description = 'Conceptos para Reporte IVA'
    _order = 'code'

    code = fields.Char(string='Código', required=True, index=True)
    description = fields.Char(string='Descripción', required=True)
    operation_type = fields.Selection([
        ('sale', 'Ventas'),
        ('purchase', 'Compras')
    ], string='Tipo de Operación', required=True, default='sale')
    value_type = fields.Selection([
        ('base', 'Base'),
        ('tax', 'Impuesto'),
        ('calculated', 'Calculado')
    ], string='Tipo de Valor', required=True, default='base')
    tax_ids = fields.Many2many('account.tax', string='Impuestos')
    calculation_formula = fields.Char(string='Fórmula de Cálculo', 
                                      help='Ejemplo: 25+11+5 para sumar los conceptos con códigos 25, 11 y 5')
    calculated_concept_ids = fields.Many2many(
        'tax.iva.concept', 
        'tax_iva_concept_calculated_rel', 
        'concept_id', 
        'calculated_concept_id', 
        string='Conceptos para Cálculo'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super(TaxIvaConcept, self).create(vals_list)
        # Forzar la validación de campos al crear registros
        for record in records:
            if record.value_type != 'calculated' and not record.tax_ids:
                raise ValidationError(_('Debe especificar al menos un impuesto para conceptos no calculados.'))
                
            if record.value_type == 'calculated' and not (record.calculation_formula or record.calculated_concept_ids):
                raise ValidationError(_('Debe especificar una fórmula de cálculo o seleccionar conceptos para el cálculo.'))
        return records
    
    @api.model
    def default_get(self, fields_list):
        """
        Sobrescribimos default_get para cargar el dominio de impuestos correctamente
        al abrir el formulario por primera vez
        """
        res = super(TaxIvaConcept, self).default_get(fields_list)
        # Si el tipo de operación está establecido (por defecto 'sale')
        if 'operation_type' in res:
            # Podríamos pre-cargar algunos impuestos aquí si fuera necesario
            # Por ahora, solo nos aseguramos de que el dominio se aplique correctamente
            pass
        return res
    
    @api.onchange('code')
    def _onchange_code(self):
        # Aquí se implementará la lógica para filtrar la descripción basado en el Excel
        # Esto requiere la estructura de datos del Excel mencionado
        pass
    
    @api.onchange('description')
    def _onchange_description(self):
        # Aquí se implementará la lógica para seleccionar el código basado en el Excel
        # Esto requiere la estructura de datos del Excel mencionado
        pass
    
    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        # Limpiar los impuestos seleccionados al cambiar el tipo de operación
        self.tax_ids = [(5, 0, 0)]
        return {}
    
    @api.onchange('value_type')
    def _onchange_value_type(self):
        """
        Gestiona los cambios en el campo 'value_type'
        - Si NO es 'calculated': limpia los campos de cálculo
        - Si ES 'calculated': limpia los impuestos
        """
        if self.value_type != 'calculated':
            self.calculation_formula = False
            self.calculated_concept_ids = False
        else:
            # Si cambia a calculado, limpiar los impuestos
            self.tax_ids = [(5, 0, 0)]
        return {}
            
    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('El código %s ya existe en otro concepto.') % record.code)
                
    @api.constrains('value_type', 'calculation_formula', 'calculated_concept_ids')
    def _check_calculation_formula(self):
        for record in self:
            if record.value_type == 'calculated' and not (record.calculation_formula or record.calculated_concept_ids):
                raise ValidationError(_('Debe especificar una fórmula de cálculo o seleccionar conceptos para el cálculo.'))
                
    @api.constrains('tax_ids', 'value_type')
    def _check_tax_ids_required(self):
        for record in self:
            if record.value_type != 'calculated' and not record.tax_ids:
                raise ValidationError(_('Debe especificar al menos un impuesto para conceptos no calculados.'))

    def calculate_value(self, date_from, date_to):
        """
        Calcular el valor del concepto según la lógica definida en los requisitos
        """
        self.ensure_one()
        
        if self.value_type == 'calculated':
            return self._calculate_formula(date_from, date_to)
        
        domain = [
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('move_id.state', '=', 'posted'),
        ]
        
        aml_obj = self.env['account.move.line']
        tax_ids = self.tax_ids.ids
        result = 0
        
        # Caso a: Impuestos tipo Venta e is_refund = False
        if self.operation_type == 'sale' and tax_ids:
            if self.value_type == 'base':
                lines = aml_obj.search(domain + [
                    ('tax_ids', 'in', tax_ids),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_receipt']),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = (debit - credit) * -1
                
            elif self.value_type == 'tax':
                lines = aml_obj.search(domain + [
                    ('tax_line_id', 'in', tax_ids),
                    ('move_id.move_type', 'in', ['out_invoice', 'out_receipt']),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = (debit - credit) * -1
        
        # Caso b: Impuestos tipo Compra e is_refund = True
        elif self.operation_type == 'purchase' and tax_ids:
            if self.value_type == 'base':
                lines = aml_obj.search(domain + [
                    ('tax_ids', 'in', tax_ids),
                    ('move_id.move_type', 'in', ['in_refund']),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = (debit - credit) * -1
                
            elif self.value_type == 'tax':
                lines = aml_obj.search(domain + [
                    ('tax_line_id', 'in', tax_ids),
                    ('move_id.move_type', 'in', ['in_refund']),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = (debit - credit) * -1
        
        # Caso c: Resto de casos
        else:
            if self.value_type == 'base':
                lines = aml_obj.search(domain + [
                    ('tax_ids', 'in', tax_ids),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = debit - credit
                
            elif self.value_type == 'tax':
                lines = aml_obj.search(domain + [
                    ('tax_line_id', 'in', tax_ids),
                ])
                debit = sum(lines.mapped('debit'))
                credit = sum(lines.mapped('credit'))
                result = debit - credit
                
        # Regla especial para conceptos específicos
        if self.code in ['82', '83', '86', '88', '89'] and result < 0:
            result = 0
            
        return result
    
    def _calculate_formula(self, date_from, date_to):
        """
        Calcular el valor de un concepto basado en su fórmula
        """
        result = 0
        
        # Calcular basado en fórmula (ejemplo: "25+11+5")
        if self.calculation_formula:
            try:
                # Dividir la fórmula en segmentos separados por operadores
                formula_parts = []
                current_code = ""
                for char in self.calculation_formula:
                    if char.isdigit():
                        current_code += char
                    elif char in ['+', '-'] and current_code:
                        formula_parts.append(current_code)
                        formula_parts.append(char)
                        current_code = ""
                
                if current_code:  # Añadir el último código
                    formula_parts.append(current_code)
                
                # Calcular el valor basado en la fórmula
                temp_result = 0
                operation = '+'
                
                for part in formula_parts:
                    if part in ['+', '-']:
                        operation = part
                    else:
                        concept = self.search([('code', '=', part)], limit=1)
                        if concept:
                            value = concept.calculate_value(date_from, date_to)
                            if operation == '+':
                                temp_result += value
                            elif operation == '-':
                                temp_result -= value
                                
                result = temp_result
            except Exception as e:
                self.message_post(body=_('Error al calcular la fórmula: %s') % str(e))
        
        # Calcular basado en conceptos seleccionados (suma simple)
        for concept in self.calculated_concept_ids:
            result += concept.calculate_value(date_from, date_to)
            
        return result