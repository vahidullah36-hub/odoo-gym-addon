from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gym_allowed_minutes = fields.Integer(
        string='Varsayılan Kullanım Süresi (Dakika)',
        default=60,
        config_parameter='gym_management.allowed_minutes',
        help='Öğrencilerin spor salonunda kalabileceği maksimum süre (dakika cinsinden)',
    )