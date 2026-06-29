{
    'name': 'Gym Management - Spor Salonu Takip Sistemi',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': 'Üniversite spor salonu öğrenci giriş/çıkış takip sistemi',
    'description': """
        Spor Salonu Öğrenci Takip Sistemi
        ==================================
        * QR kod ile öğrenci girişi
        * Otomatik süre takibi
        * Gece 00:00 otomatik çıkış (Cron Job)
        * PDF Raporlama ve Dashboard
    """,
    'author': 'Gym Management',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'portal', 'web', 'website'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron.xml',
        'views/gym_visit_views.xml',
        'views/dashboard_views.xml',
        'views/settings_views.xml',
        'views/menu_views.xml',
        'views/portal_templates.xml',
        'views/gym_announcement_views.xml',
        'views/res_config_settings_views.xml',
        'report/report.xml',
        'report/report_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gym_management/static/src/js/dashboard.js',
            'gym_management/static/src/css/gym_style.css',
            'gym_management/static/src/js/gym_auto_refresh.js',
        ],
        'web.assets_frontend': [
            'gym_management/static/src/css/portal_style.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}