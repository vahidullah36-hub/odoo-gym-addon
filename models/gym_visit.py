from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import qrcode
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)


class GymVisit(models.Model):
    _name = 'gym.visit'
    _description = 'Spor Salonu Ziyareti'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in_time desc'

    name = fields.Char(
        string='Referans',
        readonly=True,
        default=lambda self: _('Yeni'),
        copy=False,
        tracking=True,
    )
    student_name = fields.Char(string='Ad', required=True, tracking=True)
    student_surname = fields.Char(string='Soyad', required=True, tracking=True)
    full_name = fields.Char(string='Ad Soyad', compute='_compute_full_name', store=True)
    student_number = fields.Char(string='Öğrenci Numarası', required=True, tracking=True)
    department = fields.Char(string='Bölüm', required=True, tracking=True)

    check_in_time = fields.Datetime(string='Giriş Saati', default=fields.Datetime.now, required=True, tracking=True)
    check_out_time = fields.Datetime(string='Çıkış Saati', tracking=True)

    allowed_minutes = fields.Integer(string='İzin Verilen Süre (dk)', default=60)
    elapsed_minutes = fields.Integer(string='Geçen Süre (dk)', compute='_compute_times')
    remaining_minutes = fields.Integer(string='Kalan Süre (dk)', compute='_compute_times')
    total_minutes = fields.Integer(string='Toplam Kullanım (dk)', readonly=True)

    state = fields.Selection([
        ('active', 'İçeride'),
        ('expired', 'Süresi Doldu'),
        ('checked_out', 'Çıkış Yapıldı'),
    ], string='Durum', default='active', tracking=True)

    color_state = fields.Selection([
        ('green', 'Yeşil - Devam Ediyor'),
        ('yellow', 'Sarı - Son 10 Dakika'),
        ('red', 'Kırmızı - Süresi Doldu'),
    ], string='Renk Durumu', compute='_compute_times')

    kanban_color = fields.Integer(string='Kanban Rengi', compute='_compute_times')

    qr_code_image = fields.Binary(
        string='QR Kod',
        compute='_compute_qr_code',
        store=True,
    )

    qr_code_url = fields.Char(
        string='QR Kod URL',
        compute='_compute_qr_code',
        store=True,
    )

    @api.depends('student_name', 'student_surname', 'student_number', 'department', 'check_in_time')
    def _compute_qr_code(self):
        """Compute a QR code image (PNG, base64 bytes) and a simple register URL per record."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        for rec in self:
            register_url = f"{base_url}/gym/register"
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(register_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                qr_image = base64.b64encode(buffer.getvalue())
            except Exception as e:
                _logger.error('QR kod oluşturulamadı: %s', e)
                qr_image = False
            rec.qr_code_url = register_url
            rec.qr_code_image = qr_image

    @api.depends('student_name', 'student_surname')
    def _compute_full_name(self):
        for rec in self:
            rec.full_name = f"{rec.student_name or ''} {rec.student_surname or ''}".strip()

    @api.depends('check_in_time', 'allowed_minutes', 'state')
    def _compute_times(self):
        from datetime import datetime
        now = datetime.now()
        for rec in self:
            if rec.state == 'checked_out':
                rec.elapsed_minutes = rec.total_minutes or 0
                rec.remaining_minutes = 0
                rec.color_state = 'red'
                rec.kanban_color = 1
                continue

            if not rec.check_in_time:
                rec.elapsed_minutes = 0
                rec.remaining_minutes = rec.allowed_minutes or 60
                rec.color_state = 'green'
                rec.kanban_color = 10
                continue

            # Normalize check_in to a datetime instance
            if isinstance(rec.check_in_time, str):
                try:
                    # Prefer Odoo helper if available
                    if hasattr(fields.Datetime, 'to_datetime'):
                        check_in = fields.Datetime.to_datetime(rec.check_in_time)
                    elif hasattr(fields.Datetime, 'from_string'):
                        check_in = fields.Datetime.from_string(rec.check_in_time)
                    else:
                        check_in = datetime.fromisoformat(rec.check_in_time)
                except Exception:
                    # Fallback - keep raw value (will likely raise later)
                    check_in = rec.check_in_time
            else:
                check_in = rec.check_in_time
            elapsed = int((now - check_in).total_seconds() / 60)
            allowed = rec.allowed_minutes or 60
            remaining = allowed - elapsed

            rec.elapsed_minutes = max(0, elapsed)
            rec.remaining_minutes = max(0, remaining)

            if remaining <= 0:
                rec.color_state = 'red'
                rec.kanban_color = 1
                if rec.state == 'active':
                    rec.state = 'expired'
            elif remaining <= 10:
                rec.color_state = 'yellow'
                rec.kanban_color = 3
            else:
                rec.color_state = 'green'
                rec.kanban_color = 10

    def action_check_out(self):
        """Mark the student as checked out."""
        for rec in self:
            if rec.state == 'checked_out':
                raise UserError('Bu öğrenci zaten çıkış yapmış.')
            from datetime import datetime
            now = datetime.now()
            # Normalize check_in for subtraction
            if isinstance(rec.check_in_time, str):
                try:
                    if hasattr(fields.Datetime, 'to_datetime'):
                        check_in = fields.Datetime.to_datetime(rec.check_in_time)
                    elif hasattr(fields.Datetime, 'from_string'):
                        check_in = fields.Datetime.from_string(rec.check_in_time)
                    else:
                        check_in = datetime.fromisoformat(rec.check_in_time)
                except Exception:
                    raise UserError(_('Giriş saati geçersiz, çıkış yapılamıyor.'))
            else:
                check_in = rec.check_in_time
            total = int((now - check_in).total_seconds() / 60)
            rec.write({
                'check_out_time': now,
                'state': 'checked_out',
                'total_minutes': total,
            })

    def action_print_qr(self):
        """Generate QR image and open the QR report preview page."""
        self._compute_qr_code()
        self.invalidate_recordset(['qr_code_image', 'qr_code_url'])
        return {
            'type': 'ir.actions.act_url',
            'url': '/gym/qr/print',
            'target': 'new',
        }

    @api.model
    def action_open_qr(self):
        record = self.search(
            [('student_number', '=', '0000')],
            limit=1
        )

        if not record:
            record = self.create({
                'student_name': 'QR',
                'student_surname': 'Kod',
                'student_number': '0000',
                'department': 'Sistem',
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'QR Kod',
            'res_model': 'gym.visit',
            'res_id': record.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'gym_management.view_gym_qr_form'
            ).id,
            'target': 'new',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Yeni')) == _('Yeni'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gym.visit') or _('Yeni')
            config = self.env['ir.config_parameter'].sudo()
            allowed = int(config.get_param('gym_management.allowed_minutes', default=60))
            vals['allowed_minutes'] = allowed
        return super().create(vals_list)