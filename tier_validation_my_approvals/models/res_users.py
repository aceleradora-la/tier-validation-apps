# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

_INBOX_ACTION = "tier_validation_my_approvals.action_my_approvals_to_approve"


class ResUsers(models.Model):
    _inherit = "res.users"

    def _my_approvals_digest_reviews(self):
        """Lo que le toca aprobar ahora al usuario.

        Es la misma búsqueda del menú «Por aprobar»: con el usuario real, para
        que apliquen el turno de cada documento y el filtro de acceso.
        """
        self.ensure_one()
        return (
            self.env["tier.review"]
            .with_user(self)
            .search([("can_review_mine", "=", True)], order="create_date, id")
        )

    def _my_approvals_inbox_url(self, review=None):
        self.ensure_one()
        url = f"{self.get_base_url()}/odoo/action-{_INBOX_ACTION}"
        return f"{url}/{review.id}" if review else url

    def _my_approvals_digest_groups(self):
        """Pendientes por tipo de documento, listos para la plantilla.

        Una fila por documento: el enlace lleva a la aprobación en la bandeja
        y no al documento, que el aprobador puede no tener permiso de abrir.
        """
        self.ensure_one()
        reviews = (
            self._my_approvals_digest_reviews().sudo().with_context(lang=self.lang)
        )
        today = fields.Date.context_today(self)
        groups = {}
        for (model, _res_id), document_reviews in reviews.grouped(
            lambda review: (review.model, review.res_id)
        ).items():
            review = document_reviews[0]
            group = groups.setdefault(review.res_model_id.name or model, [])
            group.append(
                {
                    "name": review.res_name or "",
                    "url": self._my_approvals_inbox_url(review),
                    "requested_by": review.requested_by.name or "",
                    "days": (today - review.create_date.date()).days,
                }
            )
        return [{"name": name, "rows": groups[name]} for name in sorted(groups)]

    def _my_approvals_send_digest(self):
        """Enviar el resumen a los usuarios de `self` que tengan algo que aprobar.

        Devuelve a cuántos se les envió. Si falla el de un usuario, se sigue
        con los demás.
        """
        template = self.env.ref(
            "tier_validation_my_approvals.mail_template_my_approvals_digest",
            raise_if_not_found=False,
        )
        if not template:
            return 0
        sent = 0
        for user in self:
            if not user._my_approvals_digest_reviews():
                continue
            try:
                with self.env.cr.savepoint():
                    # force_send=False: el despacho queda a cargo del cron de correo.
                    template.send_mail(user.id, force_send=False)
            except Exception:
                _logger.exception(
                    "No se pudo enviar el resumen de aprobaciones a %s.", user.login
                )
                continue
            sent += 1
        return sent
