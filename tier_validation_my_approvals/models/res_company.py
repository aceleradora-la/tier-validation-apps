# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    my_approvals_digest_active = fields.Boolean(
        string="Enviar resumen diario",
        help="Envía todos los días a cada usuario un correo con lo que le toca "
        "aprobar. A quien no tiene nada pendiente no se le envía.",
    )
    my_approvals_digest_hour = fields.Float(
        string="Hora de envío",
        default=8.0,
        help="Hora del día a partir de la cual se envía, en la zona horaria del "
        "contacto de la compañía.",
    )
    # Fecha local, no un datetime en UTC: con una hora de envío nocturna, el
    # día UTC ya es el siguiente y el resumen de ese día no saldría.
    my_approvals_digest_last_date = fields.Date(
        string="Último resumen enviado",
        readonly=True,
        copy=False,
    )

    def _my_approvals_digest_now(self):
        """Hora local de la compañía.

        El cron corre como OdooBot, que normalmente no tiene zona horaria: sin
        esto la hora de envío se interpretaría en UTC.
        """
        self.ensure_one()
        tz = self.partner_id.tz or self.env.user.tz or "UTC"
        return fields.Datetime.context_timestamp(
            self.with_context(tz=tz), fields.Datetime.now()
        )

    def _my_approvals_digest_is_due(self, now):
        self.ensure_one()
        if not self.my_approvals_digest_active:
            return False
        if now.hour + now.minute / 60.0 < (self.my_approvals_digest_hour or 0.0):
            return False
        last = self.my_approvals_digest_last_date
        return not last or last < now.date()

    def _my_approvals_digest_recipients(self):
        """Usuarios internos con aprobaciones abiertas, por compañía principal.

        Es la lista de candidatos: si a un usuario le toca algo ahora lo define
        `res.users._my_approvals_digest_reviews`. Los usuarios de portal
        quedan afuera porque no tienen acceso a la bandeja.
        """
        self.ensure_one()
        reviews = (
            self.env["tier.review"]
            .sudo()
            .search([("status", "in", ("waiting", "pending"))])
        )
        return reviews.reviewer_ids.filtered(
            lambda user: user.active
            and not user.share
            and user.email
            and user.company_id == self
        )

    @api.model
    def _cron_my_approvals_digest(self):
        """Punto de entrada del cron horario del resumen."""
        for company in self.search([("my_approvals_digest_active", "=", True)]):
            now = company._my_approvals_digest_now()
            if not company._my_approvals_digest_is_due(now):
                continue
            try:
                recipients = company._my_approvals_digest_recipients()
                sent = recipients._my_approvals_send_digest()
            except Exception:
                # Un fallo en una compañía no puede cortar el resto de la corrida.
                _logger.exception(
                    "No se pudo enviar el resumen de aprobaciones de %s.",
                    company.display_name,
                )
                continue
            company.my_approvals_digest_last_date = now.date()
            _logger.info(
                "Resumen de aprobaciones enviado a %s usuarios (%s).",
                sent,
                company.display_name,
            )
        return True
