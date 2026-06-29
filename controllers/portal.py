from odoo import http, fields
from odoo.http import request
import os
import qrcode
import base64
from io import BytesIO
from datetime import datetime, time
import pytz

class GymPortalController(http.Controller):

    @http.route('/gym/register', type='http', auth='public', website=True, csrf=True)
    def gym_register(self, **kwargs):
        if request.httprequest.method == 'POST':
            student_name = kwargs.get('student_name', '').strip()
            student_surname = kwargs.get('student_surname', '').strip()
            student_number = kwargs.get('student_number', '').strip()
            department = kwargs.get('department', '').strip()
            gender = kwargs.get('gender', '')
            
            phone_code = kwargs.get('phone_code', '+90').strip()
            phone_raw = kwargs.get('phone', '').strip()
            full_phone = f"{phone_code} {phone_raw}" if phone_raw else ""

            phone2_code = kwargs.get('phone2_code', '+90').strip()
            phone2_raw = kwargs.get('phone2', '').strip()
            full_phone2 = f"{phone2_code} {phone2_raw}" if phone2_raw else ""
            
            blood_type = kwargs.get('blood_type', '')
            address = kwargs.get('address', '').strip()
            medical_conditions = kwargs.get('medical_conditions', '').strip()

            if not all([student_name, student_surname, student_number, department, gender]):
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Lütfen zorunlu alanları doldurun.',
                })

            existing_member = request.env['gym.visit'].sudo().search([('student_number', '=', student_number)], limit=1)
            if existing_member:
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Bu öğrenci numarası zaten sisteme kayıtlı! Lütfen "GİRİŞ YAP" sekmesini kullanın.',
                })

            request.env['gym.visit'].sudo().create({
                'student_name': student_name,
                'student_surname': student_surname,
                'student_number': student_number,
                'department': department,
                'gender': gender,  
                'phone': full_phone,
                'phone2': full_phone2,
                'blood_type': blood_type,
                'address': address,
                'medical_conditions': medical_conditions,
                'state': 'checked_out',
                'check_out_time': fields.Datetime.now(),
                'total_minutes': 0,
            })

            return request.render('gym_management.gym_portal_main_page', {
                'register_success': True,
            })

        return request.render('gym_management.gym_portal_main_page', {})


    @http.route('/gym/login', type='http', auth='public', website=True, csrf=True)
    def gym_login(self, **kwargs):
        is_gym_open = request.env['ir.config_parameter'].sudo().get_param('gym_management.is_gym_open') == 'True'
        if not is_gym_open:
            return request.render('gym_management.gym_portal_main_page', {
                'error': 'Spor salonu şu anda kapalıdır. Lütfen daha sonra tekrar deneyin.',
            })

        if request.httprequest.method == 'POST':
            student_number = kwargs.get('student_number', '').strip()

            if not student_number:
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Lütfen öğrenci numaranızı girin.',
                })

            member_profile = request.env['gym.visit'].sudo().search([
                ('student_number', '=', student_number)
            ], order='id asc', limit=1)

            if not member_profile:
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Sistemde kaydınız bulunamadı. Lütfen önce "KAYIT OL" sekmesinden bilgilerinizi giriniz.',
                })

            current_active_visit = request.env['gym.visit'].sudo().search([
                ('student_number', '=', student_number),
                ('state', 'in', ['active', 'expired']),
                ('id', '!=', member_profile.id)
            ], limit=1)

            if current_active_visit:
                return request.render('gym_management.gym_portal_main_page', {
                    'success': True,
                    'visit': current_active_visit,
                })

            tz = pytz.timezone('Europe/Istanbul')
            local_now = datetime.now(tz)
            local_midnight = tz.localize(datetime.combine(local_now.date(), time(0, 0, 0)))
            utc_midnight = local_midnight.astimezone(pytz.UTC).replace(tzinfo=None)

            today_visit = request.env['gym.visit'].sudo().search([
                ('student_number', '=', student_number),
                ('check_in_time', '>=', utc_midnight),
                ('id', '!=', member_profile.id) 
            ], limit=1)

            if today_visit:
                if member_profile.allow_reentry:
                    member_profile.sudo().write({'allow_reentry': False})
                else:
                    return request.render('gym_management.gym_portal_main_page', {
                        'error': 'Bugün için giriş hakkınızı kullandınız. Yeni giriş hakkınız gece 00:00\'da yenilenecektir.',
                    })

            blood_type = request.env['gym.visit'].sudo()._normalize_blood_type_value(member_profile.blood_type)

            active_visit = request.env['gym.visit'].sudo().create({
                'student_name': member_profile.student_name,
                'student_surname': member_profile.student_surname,
                'student_number': student_number,
                'department': member_profile.department,
                'gender': member_profile.gender,
                'phone': member_profile.phone,
                'phone2': member_profile.phone2,
                'blood_type': blood_type,
                'address': member_profile.address,
                'medical_conditions': member_profile.medical_conditions,
            })

            return request.render('gym_management.gym_portal_main_page', {
                'success': True,
                'visit': active_visit,
            })

        return request.render('gym_management.gym_portal_main_page', {})


    @http.route('/gym/profile/update', type='http', auth='public', website=True, csrf=True)
    def gym_profile_update(self, **kwargs):
        if request.httprequest.method != 'POST':
            return request.redirect('/gym/register')

        try:
            visit_id = int(kwargs.get('visit_id') or 0)
        except (TypeError, ValueError):
            visit_id = 0
        student_number = kwargs.get('student_number', '').strip()

        visit = request.env['gym.visit'].sudo().search([
            ('id', '=', visit_id),
            ('student_number', '=', student_number),
            ('state', 'in', ['active', 'expired']),
        ], limit=1)

        if not visit:
            return request.render('gym_management.gym_portal_main_page', {
                'error': 'Aktif giriş kaydınız bulunamadı. Lütfen tekrar giriş yapın.',
            })

        vals = {
            'phone': kwargs.get('phone', '').strip(),
            'phone2': kwargs.get('phone2', '').strip(),
            'address': kwargs.get('address', '').strip(),
            'medical_conditions': kwargs.get('medical_conditions', '').strip(),
        }

        member_profile = request.env['gym.visit'].sudo().search([
            ('student_number', '=', student_number)
        ], order='id asc', limit=1)

        (visit | member_profile).sudo().write(vals)

        return request.render('gym_management.gym_portal_main_page', {
            'success': True,
            'profile_update_success': True,
            'visit': visit,
        })


    @http.route('/gym/checkout', type='http', auth='public', website=True, csrf=True)
    def gym_checkout(self, **kwargs):
        if request.httprequest.method == 'POST':
            student_number = kwargs.get('student_number', '').strip()

            if not student_number:
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Lütfen öğrenci numaranızı girin.',
                })

            current_active_visit = request.env['gym.visit'].sudo().search([
                ('student_number', '=', student_number),
                ('state', 'in', ['active', 'expired'])
            ], limit=1)

            if current_active_visit:
                current_active_visit.action_check_out()
                return request.render('gym_management.gym_portal_main_page', {
                    'checkout_success': True,
                })
            else:
                return request.render('gym_management.gym_portal_main_page', {
                    'error': 'Sistemde aktif bir girişiniz bulunamadı. Şu an salonda görünmüyorsunuz.',
                })

        return request.render('gym_management.gym_portal_main_page', {})


    @http.route('/gym/qr', type='http', auth='user')
    def gym_qr_image(self, **kwargs):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        register_url = f"{base_url}/gym/register"
        try:
            import qrcode
        except Exception as e:
            return request.make_response(str(e), headers=[('Content-Type', 'text/plain')], status=500)
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(register_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return request.make_response(buffer.read(), headers=[('Content-Type', 'image/png')])

    @http.route('/gym/static/ostim_logo.png', type='http', auth='public', website=True)
    def gym_logo(self, **kwargs):
        try:
            base_dir = os.path.dirname(__file__)
            img_path = os.path.abspath(os.path.join(base_dir, '..', 'static', 'src', 'img', 'ostim_logo.png'))
            with open(img_path, 'rb') as f:
                data = f.read()
            return request.make_response(data, headers=[('Content-Type', 'image/png'), ('Content-Length', str(len(data)))])
        except Exception as e:
            return request.make_response(str(e), headers=[('Content-Type', 'text/plain')], status=500)

    @http.route('/gym/qr/print', type='http', auth='user')
    def gym_qr_print(self, **kwargs):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        register_url = f"{base_url}/gym/register"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(register_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        html = f"""
        <html>
            <head>
                <title>QR Kodu Yazdir</title>
                <style>
                    @media print {{
                        @page {{ margin: 0; }}
                        body {{ margin: 1.5cm; }}
                    }}
                </style>
            </head>
            <body onload="window.print();" style="text-align: center; margin-top: 40px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
                
                <h1 style="color: #1a2456; font-size: 38px; font-weight: 900; margin-bottom: 10px; text-transform: uppercase;">SPOR SALONU GİRİŞİ VE ÇIKIŞI</h1>
                <p style="color: #555; font-size: 18px; margin-bottom: 40px;">Kameranızı okutarak sisteme giriş ve çıkış yapabilirsiniz.</p>
                
                <img src="data:image/png;base64,{qr_base64}" style="width: 380px; height: 400px; border: 4px solid #1a2456; border-radius: 12px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);"/>
                
                <p style="margin-top: 20px; font-size: 16px; font-weight: bold; color: #8b1a3a;">{register_url}</p>
                
                <div style="margin-top: 45px;">
                    <img src="/gym_management/static/src/img/ostim_logo.png" style="height: 260px; width: auto; object-fit: contain;" alt="OSTİM Teknik Üniversitesi"/>
                </div>
                
            </body>
        </html>
        """
        return request.make_response(html)

    @http.route('/gym/tv', type='http', auth='public', website=True)
    def gym_tv_display(self, **kwargs):
        active_visits = request.env['gym.visit'].sudo().search([
            ('state', 'in', ['active', 'expired']),
            ('student_number', '!=', '0000')
        ], order='check_in_time asc')
        
        # GÜNCELLEME: Veritabanından TV'de gösterilecek aktif duyuruları çekiyoruz
        announcements = request.env['gym.announcement'].sudo().search([('active', '=', True)])
        
        return request.render('gym_management.gym_tv_display_page', {
            'visits': active_visits,
            'announcements': announcements,
        })
