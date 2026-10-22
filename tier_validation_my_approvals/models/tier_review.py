# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_OPEN_STATUSES = ("waiting", "pending")


class TierReview(models.Model):
    _inherit = "tier.review"

    # Tipo de documento genérico: sirve para filtrar, agrupar y armar el
    # pivote sin registrar cada modelo a mano.
    res_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Tipo de documento",
        compute="_compute_res_model_id",
        store=True,
        index=True,
        ondelete="set null",
    )
    can_review_mine = fields.Boolean(
        string="Me toca",
        compute="_compute_can_review_mine",
        search="_search_can_review_mine",
        help="La revisión está abierta, el usuario actual es aprobador y ya le "
        "llegó el turno según la secuencia del documento.",
    )
    approval_qty = fields.Integer(
        string="Cantidad",
        default=1,
        required=True,
        aggregator="sum",
        help="Medida fija para pivote/gráficos (1 por validación).",
    )
    approval_duration_days = fields.Float(
        string="Días hasta aprobación",
        compute="_compute_approval_duration_days",
        store=True,
        aggregator="avg",
        help="Días entre la creación de la revisión (solicitud) y su aprobación. "
        "Solo se calcula para revisiones aprobadas; el resto queda en 0. "
        "Medida para promediar tiempos de aprobación en pivote/gráficos "
        "(filtrar status='approved' para evitar sesgo por los ceros).",
    )

    @api.depends("model")
    def _compute_res_model_id(self):
        IrModel = self.env["ir.model"].sudo()
        for rec in self:
            rec.res_model_id = IrModel._get(rec.model) if rec.model else False

    @api.depends("status", "reviewed_date", "create_date")
    def _compute_approval_duration_days(self):
        for rec in self:
            if rec.status == "approved" and rec.reviewed_date and rec.create_date:
                delta = rec.reviewed_date - rec.create_date
                rec.approval_duration_days = delta.total_seconds() / 86400.0
            else:
                rec.approval_duration_days = 0.0

    @api.depends_context("uid")
    @api.depends("status", "sequence", "reviewer_ids")
    def _compute_can_review_mine(self):
        # El turno lo decide el documento (_get_sequences_to_approve): cada
        # modelo puede acotarlo, p. ej. a la etapa actual del expediente.
        user = self.env.user
        open_reviews = self.filtered(
            lambda r: r.status in _OPEN_STATUSES and user in r.reviewer_ids
        )
        (self - open_reviews).can_review_mine = False
        by_document = open_reviews.grouped(lambda r: (r.model, r.res_id))
        for (model, res_id), reviews in by_document.items():
            document = self._my_approvals_document_sudo(model, res_id)
            if document is None or not hasattr(document, "_get_sequences_to_approve"):
                sequences = []
            else:
                sequences = document._get_sequences_to_approve(user)
            for review in reviews:
                review.can_review_mine = review.sequence in sequences

    @api.model
    def _search_can_review_mine(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Operación no soportada."))
        mine = self.search(
            [
                ("reviewer_ids", "in", self.env.uid),
                ("status", "in", _OPEN_STATUSES),
            ]
        ).filtered("can_review_mine")
        positive = (operator == "=") == value
        return [("id", "in" if positive else "not in", mine.ids)]

    @api.model
    def _my_approvals_document_sudo(self, model, res_id):
        if not model or not res_id or model not in self.env:
            return None
        return self.env[model].sudo().browse(res_id).exists() or None

    def _my_approvals_document(self):
        """Documento de la revisión, con el usuario actual."""
        self.ensure_one()
        if not self._my_approvals_document_sudo(self.model, self.res_id):
            raise UserError(self.env._("El documento de esta revisión ya no existe."))
        return self.env[self.model].browse(self.res_id)

    def _my_approvals_check_turn(self):
        self.ensure_one()
        if not self.can_review_mine:
            raise UserError(
                self.env._("Esta revisión no está esperando tu aprobación ahora.")
            )

    def action_my_approvals_validate(self):
        """Aprobar desde la bandeja, con las reglas del documento de origen."""
        self._my_approvals_check_turn()
        return self._my_approvals_document().validate_tier()

    def action_my_approvals_reject(self):
        """Rechazar desde la bandeja, con las reglas del documento de origen."""
        self._my_approvals_check_turn()
        return self._my_approvals_document().reject_tier()

    def action_my_approvals_validate_bulk(self):
        """Aprobar en lote las revisiones seleccionadas que me tocan ahora.

        Se aprueba una vez por documento (validate_tier ya aprueba todas mis
        revisiones consecutivas). Se saltean las que no me tocan y las que
        piden comentario, que se aprueban de a una. Si un documento falla, se
        informa y se sigue con el resto.
        """
        mine = self.filtered("can_review_mine")
        skipped = self - mine
        approved = need_comment = self.browse()
        failed = []
        for reviews in mine.grouped(lambda r: (r.model, r.res_id)).values():
            document = reviews[0]._my_approvals_document()
            if document.has_comment:
                need_comment |= reviews
                continue
            try:
                with self.env.cr.savepoint():
                    document.validate_tier()
            except (AccessError, UserError, ValidationError) as error:
                failed.append(f"{reviews[0].res_name}: {error.args[0]}")
                continue
            approved |= reviews
        return self._my_approvals_bulk_notification(
            approved, need_comment, failed, skipped
        )

    def _my_approvals_bulk_notification(self, approved, need_comment, failed, skipped):
        _ = self.env._
        lines = [_("Aprobadas: %s.", len(approved))]
        if need_comment:
            lines.append(
                _(
                    "Piden comentario (aprobalas de a una): %s.",
                    ", ".join(need_comment.mapped("res_name")),
                )
            )
        if failed:
            lines.append(_("No se pudieron aprobar: %s.", "; ".join(failed)))
        if skipped:
            lines.append(_("No te tocan ahora: %s.", len(skipped)))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Aprobar seleccionadas"),
                "message": " ".join(lines),
                "type": "success" if approved and not failed else "warning",
                "sticky": bool(need_comment or failed),
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
