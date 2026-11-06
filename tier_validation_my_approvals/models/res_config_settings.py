# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    my_approvals_digest_active = fields.Boolean(
        related="company_id.my_approvals_digest_active", readonly=False
    )
    my_approvals_digest_hour = fields.Float(
        related="company_id.my_approvals_digest_hour", readonly=False
    )
    my_approvals_digest_last_date = fields.Date(
        related="company_id.my_approvals_digest_last_date"
    )

    def action_my_approvals_digest_test(self):
        """Enviarme el resumen ahora, sin tocar el envío diario."""
        sent = self.env.user._my_approvals_send_digest()
        if sent:
            message = self.env._("Resumen enviado a %s.", self.env.user.email)
        else:
            message = self.env._("No tenés nada por aprobar: no se envió el resumen.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Resumen diario"),
                "message": message,
                "type": "success" if sent else "warning",
            },
        }
