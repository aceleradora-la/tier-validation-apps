# Copyright 2024 ForgeFlow S.L. (https://www.forgeflow.com)
# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Tier Review Activity Board",
    "summary": "Add Tier Review Boards",
    "version": "18.0.1.0.1",
    "development_status": "Beta",
    "maintainers": ["JasminSForgeFlow"],
    "category": "Tools",
    "website": "https://github.com/aceleradora-la/tier-validation-apps",
    "author": "ForgeFlow, aceleradora.la, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "depends": ["base_tier_validation", "spreadsheet_dashboard"],
    "data": ["security/groups.xml", "views/tier_review_view.xml"],
}
