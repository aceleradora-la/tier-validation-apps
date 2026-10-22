# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Mis aprobaciones",
    "summary": "Bandeja de aprobaciones por niveles de todos los documentos",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://github.com/aceleradora-la/tier-validation-apps",
    "author": "aceleradora.la",
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "depends": ["base_tier_validation_board"],
    "data": [
        "security/my_approvals_security.xml",
        "security/ir.model.access.csv",
        "views/tier_review_views.xml",
        "views/my_approvals_menus.xml",
    ],
}
