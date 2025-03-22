{
    'name': 'Reporte IVA-300',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Reporte IVA DIAN formulario 300',
    'description': """
Reporte IVA-300
==============
Este módulo permite generar el reporte de IVA formato 300 de la DIAN.
    """,
    'author': 'FEASY SOFTWARE SOLUTIONS SAS',
    'website': 'https://esfeasy.com/',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/tax_iva_concept_views.xml',
        'wizards/tax_iva_report_wizard_views.xml',
        'wizards/import_concept_wizard_view.xml',
        'views/menu_views.xml',
        'report/tax_iva_report_template.xml',
        'report/tax_iva_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Aquí puedes agregar archivos CSS/JS si fueran necesarios
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}