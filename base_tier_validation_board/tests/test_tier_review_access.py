# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTierReviewAccess(TransactionCase):
    """Reviews are only found by users who can read the document or take
    part in the review.

    The documents are core records with known access, so no fake model is
    needed: partners hidden by a rule and a model regular users cannot read.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.approver = new_test_user(cls.env, login="board_approver")
        cls.requester = new_test_user(cls.env, login="board_requester")
        cls.decider = new_test_user(cls.env, login="board_decider")
        cls.outsider = new_test_user(cls.env, login="board_outsider")

        partner_model = cls.env["ir.model"]._get("res.partner")
        param_model = cls.env["ir.model"]._get("ir.config_parameter")
        cls.partner_definition = cls._definition(partner_model)
        cls.param_definition = cls._definition(param_model)

        # Partners named "Board secret ..." are hidden to every regular user.
        cls.env["ir.rule"].create(
            {
                "name": "Board test: hide secret partners",
                "model_id": partner_model.id,
                "domain_force": "[('name', 'not ilike', 'Board secret')]",
            }
        )
        cls.public_partner = cls.env["res.partner"].create({"name": "Board public"})
        cls.secret_partner = cls.env["res.partner"].create({"name": "Board secret"})
        # Regular users have no access at all to system parameters.
        cls.param = cls.env["ir.config_parameter"].create(
            {"key": "base_tier_validation_board.test", "value": "1"}
        )

        cls.public_review = cls._review(cls.partner_definition, cls.public_partner)
        cls.secret_review = cls._review(
            cls.partner_definition, cls.secret_partner, done_by=cls.decider.id
        )
        cls.param_review = cls._review(cls.param_definition, cls.param)
        cls.reviews = cls.public_review | cls.secret_review | cls.param_review

    @classmethod
    def _definition(cls, model):
        return cls.env["tier.definition"].create(
            {
                "name": f"Board test {model.model}",
                "model_id": model.id,
                "review_type": "individual",
                "reviewer_id": cls.approver.id,
            }
        )

    @classmethod
    def _review(cls, definition, record, **vals):
        return cls.env["tier.review"].create(
            {
                "model": record._name,
                "res_id": record.id,
                "definition_id": definition.id,
                "requested_by": cls.requester.id,
                **vals,
            }
        )

    def _search_as(self, user, reviews=None, **kwargs):
        reviews = self.reviews if reviews is None else reviews
        return (
            self.env["tier.review"]
            .with_user(user)
            .search([("id", "in", reviews.ids)], **kwargs)
        )

    def test_outsider_only_sees_readable_documents(self):
        self.assertEqual(self._search_as(self.outsider), self.public_review)

    def test_participants_see_reviews_of_unreadable_documents(self):
        # Reviewer (an approver without access to the document), requester
        # and the user who did the review.
        for user in (self.approver, self.requester):
            self.assertEqual(self._search_as(user), self.reviews, user.login)
        self.assertEqual(
            self._search_as(self.decider), self.public_review | self.secret_review
        )

    def test_participant_reads_document_name(self):
        review = self._search_as(self.approver, self.secret_review)
        self.assertEqual(review.res_name, self.secret_partner.name)

    def test_superuser_sees_everything(self):
        self.assertEqual(
            self.env["tier.review"].search([("id", "in", self.reviews.ids)]),
            self.reviews,
        )
        self.assertEqual(
            self.env["tier.review"]
            .with_user(self.outsider)
            .sudo()
            .search([("id", "in", self.reviews.ids)]),
            self.reviews,
        )

    def test_pagination_applies_once(self):
        # Interleave visible and hidden reviews so a page cut before the
        # filter would come out short or empty.
        extra = self.env["tier.review"]
        for index in range(4):
            public = self.env["res.partner"].create({"name": f"Board public {index}"})
            secret = self.env["res.partner"].create({"name": f"Board secret {index}"})
            extra |= self._review(self.partner_definition, secret)
            extra |= self._review(self.partner_definition, public)
        reviews = self.reviews | extra
        visible = self._search_as(self.outsider, reviews, order="id")
        self.assertEqual(len(visible), 5)
        for offset in (0, 2, 4):
            page = self._search_as(
                self.outsider, reviews, offset=offset, limit=2, order="id"
            )
            self.assertEqual(page.ids, visible.ids[offset : offset + 2], offset)

    def test_count_and_read_group_match_search(self):
        TierReview = self.env["tier.review"].with_user(self.outsider)
        domain = [("id", "in", self.reviews.ids)]
        self.assertEqual(TierReview.search_count(domain), 1)
        [(count,)] = TierReview._read_group(domain, aggregates=["__count"])
        self.assertEqual(count, 1)

    def test_review_of_missing_model_is_hidden(self):
        orphan = self.env["tier.review"].create(
            {
                "model": "base_tier_validation_board.missing",
                "res_id": 1,
                "definition_id": self.partner_definition.id,
            }
        )
        self.assertFalse(self._search_as(self.outsider, orphan))
        self.assertEqual(self._search_as(self.approver, orphan), orphan)

    def test_open_origin(self):
        action = self.public_review.open_origin()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.public_partner.id)
