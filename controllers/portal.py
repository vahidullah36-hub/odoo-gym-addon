from odoo import http
from odoo.http import request
import qrcode
import base64
from io import BytesIO


class GymPortalController(http.Controller):

    @http.route('/gym/register', type='http', auth='public', website=True, csrf=True)
    def gym_register(self, **kwargs):
        if request.httprequest.method == 'POST':
            student_name = kwargs.get('student_name', '').strip()
            student_surname = kwargs.get('student_surname', '').strip()
            student_number = kwargs.get('student_number', '').strip()
            department = kwargs.get('department', '').strip()

            if not all([student_name, student_surname, student_number, department]):
                return request.render('gym_management.gym_register_page', {
                    'error': 'Lutfen tum alanlari doldurun.',
                    'success': False,
                })

            config = request.env['ir.config_parameter'].sudo()
            allowed_minutes = int(config.get_param('gym_management.allowed_minutes', default=60))

            request.env['gym.visit'].sudo().create({
                'student_name': student_name,
                'student_surname': student_surname,
                'student_number': student_number,
                'department': department,
                'allowed_minutes': allowed_minutes,
            })

            return request.render('gym_management.gym_register_page', {
                'success': True,
                'allowed_minutes': allowed_minutes,
            })

        return request.render('gym_management.gym_register_page', {
            'success': False,
        })

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
        return request.make_response(
            buffer.read(),
            headers=[('Content-Type', 'image/png')]
        )

    @http.route('/gym/static/ostim_logo.png', type='http', auth='public', website=True)
    def gym_logo(self, **kwargs):
        """Serve the module's ostim_logo.png directly from disk for debugging.

        This bypasses Odoo's static content routing so we can capture a traceback
        or verify the file is readable by the server process.
        """
        try:
            # Path: controllers/ -> ../static/src/img/ostim_logo.png
            base_dir = os.path.dirname(__file__)
            img_path = os.path.abspath(os.path.join(base_dir, '..', 'static', 'src', 'img', 'ostim_logo.png'))
            with open(img_path, 'rb') as f:
                data = f.read()
            return request.make_response(data, headers=[('Content-Type', 'image/png'), ('Content-Length', str(len(data)))])
        except Exception as e:
            # Return exception body for quick debugging (visible in browser/cli)
    
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
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"/>
    <title>Spor Salonu QR Kod</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background: #fff;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            max-width: 500px;
        }}
        .title {{
            font-size: 26px;
            font-weight: 800;
            color: #1a1a2e;
            letter-spacing: 3px;
            margin-bottom: 6px;
        }}
        .subtitle {{
            font-size: 15px;
            color: #555;
            margin-bottom: 6px;
            font-weight: 600;
        }}
        .desc {{
            font-size: 12px;
            color: #999;
            margin-bottom: 30px;
        }}
        .qr-box {{
            display: inline-block;
            border: 3px solid #1a1a2e;
            border-radius: 16px;
            padding: 20px;
            background: #fff;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            margin-bottom: 24px;
        }}
        .qr-box img {{
            display: block;
            width: 220px;
            height: 220px;
        }}
        .url-box {{
            background: #f5f5f5;
            border-radius: 10px;
            padding: 12px 24px;
            margin-bottom: 30px;
            display: inline-block;
        }}
        .url-label {{
            font-size: 10px;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}
        .url-text {{
            font-size: 13px;
            color: #1a1a2e;
            font-weight: 700;
        }}
        .footer {{
            font-size: 11px;
            color: #bbb;
            line-height: 1.8;
        }}
        @media print {{
            body {{ background: #fff; }}
            .no-print {{ display: none; }}
        }}
    </style>
    <script>
        window.onload = function() {{
            window.print();
        }};
    </script>
</head>
<body>
    <div class="container">
        <div class="title">SPOR SALONU</div>
        <div class="subtitle">Öğrenci Giriş QR Kodu</div>
        <div class="desc">Telefon kameranızla okutarak giriş yapabilirsiniz.</div>

        <div class="qr-box">
            <img src="data:image/png;base64,{qr_base64}" alt="QR Kod"/>
        </div>

        <div class="url-box">
            <div class="url-label">Kayıt Adresi</div>
            <div class="url-text">{register_url}</div>
        </div>

        <div class="footer">
            Bu QR kodu spor salonunun girişine asınız.<br/>
            Üniversite Spor Merkezi - Giriş Kayıt Sistemi
        </div>
    </div>
</body>
</html>
"""
        return request.make_response(
            html,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )    
        
                