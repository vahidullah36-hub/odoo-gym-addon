from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gym_allowed_minutes = fields.Integer(
        string='Varsayılan Kullanım Süresi (Dakika)',
        default=60,
        config_parameter='gym_management.allowed_minutes',
        help='Öğrencilerin spor salonunda kalabileceği maksimum süre (dakika cinsinden)',
    )

    is_gym_open = fields.Boolean(
        string='Spor Salonu Açık',
        default=True,
        config_parameter='gym_management.is_gym_open',
        help='Kapatılırsa öğrenciler giriş yapamaz, portal sayfasında uyarı gösterilir.',
    )

    def action_open_gym(self):
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param('gym_management.is_gym_open', 'True')
        self.is_gym_open = True
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_close_gym(self):
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param('gym_management.is_gym_open', 'False')
        self.is_gym_open = False
        return {'type': 'ir.actions.client', 'tag': 'reload'}
