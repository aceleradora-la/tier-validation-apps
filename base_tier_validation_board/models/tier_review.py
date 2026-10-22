# Copyright 2024 ForgeFlow S.L.  <https://www.forgeflow.com>
# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.tools import SQL


class TierReview(models.Model):
    _inherit = "tier.review"

    @api.depends("model", "res_id")
    def _compute_res_name(self):
        for record in self:
            if record.res_id and record.model and record.model in self.env:
                record.res_name = (
                    self.env[record.model].browse(record.res_id).exists().display_name
                )
            else:
                record.res_name = False

    related_model_instance = fields.Reference(
        selection="_selection_related_model_instance",
        compute="_compute_related_model_instance",
        string="Document",
    )
    res_name = fields.Char(
        "Resource Name", compute="_compute_res_name", compute_sudo=True
    )

    @api.depends("res_id", "model")
    def _compute_related_model_instance(self):
        for record in self:
            ref = False
            if record.res_id:
                ref = f"{record.model},{record.res_id}"
            record.related_model_instance = ref

    @api.model
    def _selection_related_model_instance(self):
        models = self.env["tier.definition"].sudo().search([]).mapped("model_id")
        return [(model.model, model.name) for model in models]

    def open_origin(self):
        self.ensure_one()
        vid = self.env[self.model].browse(self.res_id).get_formview_id()
        response = {
            "type": "ir.actions.act_window",
            "res_model": self.model,
            "view_mode": "form",
            "res_id": self.res_id,
            "target": "current",
            "views": [(vid, "form")],
        }
        return response

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Only return reviews the current user is allowed to see.

        A review is visible when the user can read its document, or when the
        user takes part in it (reviewer, requester or the one who did it): an
        approver may have to decide on a document they cannot open, e.g. a
        vendor bill for an approver without accounting rights.

        The filter runs on the whole domain and the page is cut afterwards,
        so ``offset``/``limit`` are applied once. Searches as superuser (and
        ``sudo()``) skip it, so internal computations are not affected.
        ``read_group`` and ``search_count`` go through here as well.
        """
        if self.env.su:
            return super()._search(domain, offset=offset, limit=limit, order=order)
        ids = self.browse(super()._search(domain, order=order)).ids
        if ids:
            allowed = self._board_visible_ids(ids)
            ids = [review_id for review_id in ids if review_id in allowed]
        return super()._search(
            [("id", "in", ids)], offset=offset, limit=limit, order=order
        )

    @api.model
    def _board_visible_ids(self, ids):
        """Subset of ``ids`` visible to the current user (see ``_search``)."""
        # reviewer_ids is a stored computed many2many: a domain on it reads the
        # relation table without flushing it, so a review created in this
        # transaction would not be found for its reviewer.
        self.flush_model(["model", "res_id", "done_by", "requested_by", "reviewer_ids"])
        uid = self.env.uid
        visible = set(
            self.sudo()
            .search(
                [
                    ("id", "in", ids),
                    "|",
                    "|",
                    ("reviewer_ids", "in", uid),
                    ("done_by", "=", uid),
                    ("requested_by", "=", uid),
                ]
            )
            .ids
        )
        reviews_to_check = []
        for sub_ids in self.env.cr.split_for_in_conditions(set(ids) - visible):
            self.env.cr.execute(
                SQL(
                    """
                SELECT review.id, review.model, review.res_id
                FROM %(table)s review
                WHERE review.id = ANY (%(ids)s) AND review.res_id != 0""",
                    table=SQL.identifier(self._table),
                    ids=list(sub_ids),
                )
            )
            reviews_to_check += self.env.cr.dictfetchall()

        review_to_documents = {}
        for review in reviews_to_check:
            review_to_documents.setdefault(review["model"], set()).add(review["res_id"])

        for doc_model, doc_ids in review_to_documents.items():
            # A review of a model that no longer exists (uninstalled module)
            # cannot be checked: keep it hidden.
            if doc_model not in self.env:
                continue
            DocumentModel = self.env[doc_model]
            if not DocumentModel.has_access("read"):
                continue
            valid_doc_ids = set(
                DocumentModel.browse(doc_ids)._filtered_access("read").ids
            )
            visible.update(
                review["id"]
                for review in reviews_to_check
                if review["model"] == doc_model and review["res_id"] in valid_doc_ids
            )
        return visible
