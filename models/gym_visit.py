from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import qrcode
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)

BLOOD_TYPE_ALIASES = {
    'A+': 'A Rh+',
    'A-': 'A Rh-',
    'B+': 'B Rh+',
    'B-': 'B Rh-',
    'AB+': 'AB Rh+',
    'AB-': 'AB Rh-',
    '0+': '0 Rh+',
    '0-': '0 Rh-',
    'O+': '0 Rh+',
    'O-': '0 Rh-',
}

class GymVisit(models.Model):
    _name = 'gym.visit'
    _description = 'Spor Salonu Ziyareti'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in_time desc'

    name = fields.Char(string='Referans', readonly=True, default=lambda self: _('Yeni'), copy=False, tracking=True)
    student_name = fields.Char(string='Ad', required=True, tracking=True)
    student_surname = fields.Char(string='Soyad', required=True, tracking=True)
    full_name = fields.Char(string='Ad Soyad', compute='_compute_full_name', store=True)
    student_number = fields.Char(string='Öğrenci Numarası', required=True, tracking=True)
    department = fields.Char(string='Bölüm', required=True, tracking=True)

    address = fields.Text(string='Ev Adresi', tracking=True)
    phone = fields.Char(string='Telefon Numarası', tracking=True)
    phone2 = fields.Char(string='İkinci Telefon Numarası', tracking=True)
    
    blood_type = fields.Selection([
        ('A Rh+', 'A Rh+'), ('A Rh-', 'A Rh-'),
        ('B Rh+', 'B Rh+'), ('B Rh-', 'B Rh-'),
        ('AB Rh+', 'AB Rh+'), ('AB Rh-', 'AB Rh-'),
        ('0 Rh+', '0 Rh+'), ('0 Rh-', '0 Rh-'),
    ], string='Kan Grubu', tracking=True)
    
    medical_conditions = fields.Text(string='Hastalık / Sağlık Durumu', tracking=True)
    
    gender = fields.Selection([
        ('male', 'Erkek'),
        ('female', 'Kadın')
    ], string='Cinsiyet', tracking=True)
    
    allow_reentry = fields.Boolean(string="Tekrar Giriş İzni", default=False)

    check_in_time = fields.Datetime(string='Giriş Saati', default=fields.Datetime.now, required=True, tracking=True)
    check_out_time = fields.Datetime(string='Çıkış Saati', tracking=True)

    custom_allowed_minutes = fields.Integer(string='Özel Tanımlı Süre', default=0)
    allowed_minutes = fields.Integer(
        string='İzin Verilen Süre (dk)', 
        compute='_compute_allowed_minutes', 
        inverse='_inverse_allowed_minutes', 
        readonly=False
    )

    @api.depends('custom_allowed_minutes')
    def _compute_allowed_minutes(self):
        config = self.env['ir.config_parameter'].sudo()
        global_val = int(config.get_param('gym_management.allowed_minutes', default=60))
        for rec in self:
            if rec.custom_allowed_minutes > 0:
                rec.allowed_minutes = rec.custom_allowed_minutes
            else:
                rec.allowed_minutes = global_val

    def _inverse_allowed_minutes(self):
        for rec in self:
            rec.custom_allowed_minutes = rec.allowed_minutes

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

    qr_code_image = fields.Binary(string='QR Kod', compute='_compute_qr_code', store=True)
    qr_code_url = fields.Char(string='QR Kod URL', compute='_compute_qr_code', store=True)

    is_member = fields.Boolean(string='Üye Kaydı', default=False, index=True)

    @api.model
    def _update_member_status(self, student_numbers):
        for num in set(student_numbers):
            if num and num != '0000':
                visits = self.search([('student_number', '=', num)], order='id asc')
                if visits:
                    if not visits[0].is_member:
                        visits[0].is_member = True
                    for v in visits[1:]:
                        if v.is_member:
                            v.is_member = False

    @api.model
    def _normalize_blood_type_value(self, blood_type):
        return BLOOD_TYPE_ALIASES.get(blood_type, blood_type)

    def unlink(self):
        student_numbers = self.mapped('student_number')
        res = super(GymVisit, self).unlink()
        self.env['gym.visit']._update_member_status(student_numbers)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Yeni')) == _('Yeni'):
                vals['name'] = self.env['ir.sequence'].next_by_code('gym.visit') or _('Yeni')
            if vals.get('blood_type'):
                vals['blood_type'] = self._normalize_blood_type_value(vals['blood_type'])
        records = super().create(vals_list)
        self._update_member_status(records.mapped('student_number'))
        return records

    def write(self, vals):
        if vals.get('blood_type'):
            vals['blood_type'] = self._normalize_blood_type_value(vals['blood_type'])

        old_numbers = []
        if 'student_number' in vals:
            old_numbers = self.mapped('student_number')
            for rec in self:
                new_number = vals['student_number'].strip() if isinstance(vals['student_number'], str) else vals['student_number']
                vals['student_number'] = new_number
                
                if rec.student_number and rec.student_number != new_number:
                    all_related_visits = self.search([
                        ('student_number', '=', rec.student_number),
                        ('id', '!=', rec.id)
                    ])
                    if all_related_visits:
                        super(GymVisit, all_related_visits).write({'student_number': new_number})
                        
        res = super(GymVisit, self).write(vals)
        
        if 'student_number' in vals:
            new_numbers = self.mapped('student_number')
            self._update_member_status(old_numbers + new_numbers)
            
        return res

    def action_renew_entry(self):
        for rec in self:
            rec.allow_reentry = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Başarılı',
                'message': 'Giriş hakkı yenilendi! Öğrenci bugün salona tekrar giriş yapabilir.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_delete_student_entirely(self):
        for rec in self:
            if rec.student_number:
                all_visits = self.env['gym.visit'].search([('student_number', '=', rec.student_number)])
                all_visits.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.depends('student_name', 'student_surname', 'student_number', 'department', 'check_in_time')
    def _compute_qr_code(self):
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

            check_in = rec.check_in_time
            if isinstance(check_in, str):
                check_in = fields.Datetime.from_string(check_in)
            
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
        for rec in self:
            if rec.state == 'checked_out':
                raise UserError('Bu öğrenci zaten çıkış yapmış.')
            now = fields.Datetime.now()
            check_in = rec.check_in_time
            if isinstance(check_in, str):
                check_in = fields.Datetime.from_string(check_in)
            total = int((now - check_in).total_seconds() / 60)
            rec.write({
                'check_out_time': now,
                'state': 'checked_out',
                'total_minutes': total,
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def cron_auto_checkout_midnight(self):
        active_visits = self.search([('state', 'in', ['active', 'expired'])])
        for visit in active_visits:
            try:
                visit.action_check_out()
            except Exception as e:
                _logger.error('Otomatik çıkış sırasında hata: %s', e)
                pass

    def action_print_qr(self):
        self._compute_qr_code()
        self.invalidate_recordset(['qr_code_image', 'qr_code_url'])
        return {
            'type': 'ir.actions.act_url',
            'url': '/gym/qr/print',
            'target': 'new',
        }

    @api.model
    def action_open_tv_display(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/gym/tv',
            'target': 'new',
        }

    @api.model
    def action_open_qr(self):
        record = self.search([('student_number', '=', '0000')], limit=1)
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
            'view_id': self.env.ref('gym_management.view_gym_qr_form').id,
            'target': 'new',
        }
    
class ReportGymDailySummary(models.AbstractModel):
    _name = 'report.gym_management.report_gym_daily_template'
    _description = 'Günlük Ziyaret Raporu Detayları'

    @api.model
    def _get_report_values(self, docids, data=None):
        import pytz
        from datetime import datetime, time
        
        tz = pytz.timezone('Europe/Istanbul')
        local_now = datetime.now(tz)
        local_midnight = tz.localize(datetime.combine(local_now.date(), time(0, 0, 0)))
        utc_midnight = local_midnight.astimezone(pytz.UTC).replace(tzinfo=None)
        
        docs = self.env['gym.visit'].search([
            ('check_in_time', '>=', utc_midnight),
            ('student_number', '!=', '0000') 
        ], order='check_in_time asc')
        
        return {
            'doc_ids': docs.ids,
            'doc_model': 'gym.visit',
            'docs': docs,
            'total_count': len(docs),
            'active_count': len(docs.filtered(lambda r: r.state in ['active', 'expired'])),
            'checked_out_count': len(docs.filtered(lambda r: r.state == 'checked_out')),
        }

# =========================================================================
# YENİ EKLENEN: TV Duyuru Yönetimi Veritabanı Modeli
# =========================================================================
class GymAnnouncement(models.Model):
    _name = 'gym.announcement'
    _description = 'TV Duyuru Yonetimi'
    _order = 'id desc'

    name = fields.Char(string='Duyuru Metni', required=True)
    active = fields.Boolean(string='Ekranda Goster', default=True)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_gym_open = fields.Boolean(
        string="Spor Salonu Açık", 
        config_parameter='gym_management.is_gym_open',
        default=True,
        help="Kapalıysa portal üzerinden öğrenci girişleri engellenir."
    )