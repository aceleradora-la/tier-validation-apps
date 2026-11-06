# Copyright 2026 aceleradora.la
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import unittest
from datetime import date, datetime
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

try:
    # Usa odoo_test_helper para crear modelos de prueba con tier validation.
    from odoo.addons.base_tier_validation.tests.common import CommonTierValidation

    MISSING_TEST_HELPER = False
except ImportError:
    CommonTierValidation = TransactionCase
    MISSING_TEST_HELPER = True


@tagged("post_install", "-at_install")
class TestMyApprovalsSetup(TransactionCase):
    """Lo que no necesita un modelo con tier validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.user = new_test_user(cls.env, login="my_approvals_user")
        cls.partner = cls.env["res.partner"].create({"name": "Mis aprobaciones"})
        definition = cls.env["tier.definition"].create(
            {
                "name": "Mis aprobaciones test",
                "model_id": cls.env["ir.model"]._get("res.partner").id,
                "review_type": "individual",
                "reviewer_id": cls.user.id,
            }
        )
        cls.review = cls.env["tier.review"].create(
            {
                "model": "res.partner",
                "res_id": cls.partner.id,
                "definition_id": definition.id,
                "status": "pending",
            }
        )

    def test_res_model_id(self):
        self.assertEqual(self.review.res_model_id.model, "res.partner")

    def test_document_without_tier_validation(self):
        # res.partner no tiene tier validation: no hay turno ni se puede aprobar.
        review = self.review.with_user(self.user)
        self.assertFalse(review.can_review_mine)
        with self.assertRaises(UserError):
            review.action_my_approvals_validate()

    def test_bulk_without_tier_validation(self):
        # La aprobación masiva no falla: la saltea porque no le toca a nadie.
        action = self.review.with_user(self.user).action_my_approvals_validate_bulk()
        self.assertIn("No te tocan ahora: 1", action["params"]["message"])
        self.assertEqual(self.review.status, "pending")

    def test_menus_and_groups(self):
        root = self.env.ref("tier_validation_my_approvals.menu_my_approvals_root")
        self.assertTrue(root.web_icon)
        menus = (
            self.env["ir.ui.menu"]
            .with_user(self.user)
            .search([("id", "child_of", root.id)])
        )
        names = set(menus.mapped("name"))
        self.assertIn("Por aprobar", names)
        self.assertNotIn("Todas", names)
        self.assertNotIn("Configuración", names)
        manager = self.env.ref(
            "tier_validation_my_approvals.group_my_approvals_manager"
        )
        self.user.groups_id = [(4, manager.id)]
        self.env["ir.ui.menu"].invalidate_model()
        names = set(
            self.env["ir.ui.menu"]
            .with_user(self.user)
            .search([("id", "child_of", root.id)])
            .mapped("name")
        )
        self.assertTrue({"Todas", "Análisis", "Configuración"} <= names)
        # El administrador de la app edita definiciones sin Ajustes / Técnico.
        definitions = self.env["tier.definition"].with_user(self.user)
        self.assertTrue(definitions.has_access("write"))


@unittest.skipIf(MISSING_TEST_HELPER, "odoo_test_helper no está instalado")
@tagged("post_install", "-at_install")
class TestMyApprovalsFlow(CommonTierValidation):
    """Aprobar y rechazar desde la bandeja, con un modelo de prueba de OCA."""

    def setUp(self):
        super().setUp()
        # test_record (test_field=1.0) pide una sola aprobación de test_user_1.
        self.test_record.with_user(self.test_user_2).request_validation()
        self.review = self.test_record.review_ids
        self.assertEqual(len(self.review), 1)

    def _search_mine(self, user, value=True):
        return (
            self.env["tier.review"]
            .with_user(user)
            .search([("id", "=", self.review.id), ("can_review_mine", "=", value)])
        )

    def test_res_model_id(self):
        self.assertEqual(self.review.res_model_id, self.tester_model)

    def test_can_review_mine(self):
        self.assertTrue(self.review.with_user(self.test_user_1).can_review_mine)
        self.assertFalse(self.review.with_user(self.test_user_2).can_review_mine)
        self.assertEqual(self._search_mine(self.test_user_1), self.review)
        self.assertFalse(self._search_mine(self.test_user_2))
        self.assertEqual(self._search_mine(self.test_user_2, False), self.review)

    def test_to_approve_action_domain(self):
        action = self.env.ref(
            "tier_validation_my_approvals.action_my_approvals_to_approve"
        )
        domain = safe_eval(action.domain, {"uid": self.test_user_1.id})
        found = self.env["tier.review"].with_user(self.test_user_1).search(domain)
        self.assertIn(self.review, found)

    def test_validate_from_inbox(self):
        self.review.with_user(self.test_user_1).action_my_approvals_validate()
        self.assertEqual(self.review.status, "approved")
        self.assertEqual(self.review.done_by, self.test_user_1)
        self.assertTrue(self.test_record.validated)
        self.assertGreaterEqual(self.review.approval_duration_days, 0.0)
        self.assertEqual(self.review.approval_qty, 1)

    def test_reject_from_inbox(self):
        self.review.with_user(self.test_user_1).action_my_approvals_reject()
        self.assertEqual(self.review.status, "rejected")
        self.assertTrue(self.test_record.rejected)

    def test_not_my_turn(self):
        with self.assertRaises(UserError):
            self.review.with_user(self.test_user_2).action_my_approvals_validate()
        self.assertEqual(self.review.status, "pending")

    def test_turn_follows_sequence(self):
        # test_field > 3: test_user_1 (definición con secuencia 20) y
        # test_user_2 (secuencia 10). En base_tier_validation firma primero la
        # definición de mayor secuencia: test_user_1.
        record = self.test_model.create({"test_field": 4.0})
        record.with_user(self.test_user_3_multi_company).request_validation()
        first = record.review_ids.filtered(lambda r: self.test_user_1 in r.reviewer_ids)
        second = record.review_ids.filtered(
            lambda r: self.test_user_2 in r.reviewer_ids
        )
        self.assertTrue(first.with_user(self.test_user_1).can_review_mine)
        self.assertFalse(second.with_user(self.test_user_2).can_review_mine)
        first.with_user(self.test_user_1).action_my_approvals_validate()
        second.invalidate_recordset(["can_review_mine"])
        self.assertTrue(second.with_user(self.test_user_2).can_review_mine)

    def test_bulk_validate(self):
        other = self.test_model.create({"test_field": 1.0})
        other.with_user(self.test_user_2).request_validation()
        # Una revisión de test_user_1 que todavía no le toca: antes firma
        # test_user_2 (definición de mayor secuencia). 0.4 no entra en ninguna
        # definición del fixture.
        for user, sequence in ((self.test_user_2, 50), (self.test_user_1, 40)):
            self.tier_def_obj.create(
                {
                    "model_id": self.tester_model.id,
                    "review_type": "individual",
                    "reviewer_id": user.id,
                    "definition_domain": "[('test_field', '=', 0.4)]",
                    "approve_sequence": True,
                    "sequence": sequence,
                    "name": f"Turno {sequence}",
                }
            )
        later = self.test_model.create({"test_field": 0.4})
        later.with_user(self.test_user_2).request_validation()
        not_yet = later.review_ids.filtered(
            lambda r: self.test_user_1 in r.reviewer_ids
        )
        self.assertFalse(not_yet.with_user(self.test_user_1).can_review_mine)
        selected = self.review | other.review_ids | not_yet
        action = selected.with_user(
            self.test_user_1
        ).action_my_approvals_validate_bulk()
        self.assertEqual(self.review.status, "approved")
        self.assertEqual(other.review_ids.status, "approved")
        self.assertNotEqual(not_yet.status, "approved")
        message = action["params"]["message"]
        self.assertIn("Aprobadas: 2", message)
        self.assertIn("No te tocan ahora: 1", message)

    def test_bulk_skips_reviews_that_need_comment(self):
        self.tier_def_obj.create(
            {
                "model_id": self.tester_model.id,
                "review_type": "individual",
                "reviewer_id": self.test_user_1.id,
                "definition_domain": "[('test_field', '=', 0.5)]",
                "has_comment": True,
                "name": "Pide comentario",
            }
        )
        record = self.test_model.create({"test_field": 0.5})
        record.with_user(self.test_user_2).request_validation()
        review = record.review_ids
        action = review.with_user(self.test_user_1).action_my_approvals_validate_bulk()
        self.assertNotEqual(review.status, "approved")
        self.assertIn("Piden comentario", action["params"]["message"])
        self.assertTrue(action["params"]["sticky"])


@unittest.skipIf(MISSING_TEST_HELPER, "odoo_test_helper no está instalado")
@tagged("post_install", "-at_install")
class TestMyApprovalsDigest(CommonTierValidation):
    """Resumen diario: a quién le llega, qué trae y cuándo sale."""

    def setUp(self):
        super().setUp()
        self.test_user_1.email = "aprobador1@example.com"
        self.test_user_2.email = "aprobador2@example.com"
        self.company = self.test_user_1.company_id
        self.company.write(
            {
                "my_approvals_digest_active": True,
                "my_approvals_digest_hour": 8.0,
                "my_approvals_digest_last_date": False,
            }
        )
        self.test_record.with_user(self.test_user_2).request_validation()
        self.review = self.test_record.review_ids

    def _digest_mails(self, user):
        return self.env["mail.mail"].search(
            [
                ("email_to", "ilike", user.email),
                ("subject", "=", "Tenés aprobaciones pendientes"),
            ]
        )

    def _at(self, hour):
        return datetime(2026, 11, 6, hour, 0)

    def test_groups_by_document(self):
        groups = self.test_user_1._my_approvals_digest_groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["name"], self.tester_model.name)
        row = groups[0]["rows"][0]
        self.assertEqual(row["name"], self.test_record.display_name)
        self.assertEqual(row["requested_by"], self.test_user_2.name)
        self.assertEqual(row["days"], 0)
        self.assertTrue(row["url"].endswith(f"/{self.review.id}"))
        self.assertIn("action-tier_validation_my_approvals", row["url"])

    def test_nothing_pending_for_other_user(self):
        self.assertFalse(self.test_user_2._my_approvals_digest_groups())
        self.assertEqual(self.test_user_2._my_approvals_send_digest(), 0)
        self.assertFalse(self._digest_mails(self.test_user_2))

    def test_send_digest(self):
        self.assertEqual(self.test_user_1._my_approvals_send_digest(), 1)
        mail = self._digest_mails(self.test_user_1)
        self.assertEqual(len(mail), 1)
        self.assertIn(self.test_record.display_name, mail.body_html)
        self.assertIn(f"/{self.review.id}", mail.body_html)
        self.assertIn(self.tester_model.name, mail.body_html)

    def test_approved_leaves_digest(self):
        self.review.with_user(self.test_user_1).action_my_approvals_validate()
        self.assertFalse(self.test_user_1._my_approvals_digest_reviews())
        self.assertEqual(self.test_user_1._my_approvals_send_digest(), 0)

    def test_digest_follows_turn(self):
        # Con dos niveles, al segundo no le llega hasta que firme el primero.
        record = self.test_model.create({"test_field": 4.0})
        record.with_user(self.test_user_3_multi_company).request_validation()
        first = record.review_ids.filtered(lambda r: self.test_user_1 in r.reviewer_ids)
        self.assertIn(first, self.test_user_1._my_approvals_digest_reviews())
        self.assertFalse(self.test_user_2._my_approvals_digest_reviews())
        first.with_user(self.test_user_1).action_my_approvals_validate()
        self.env["tier.review"].invalidate_model(["can_review_mine"])
        self.assertTrue(self.test_user_2._my_approvals_digest_reviews())

    def test_recipients(self):
        recipients = self.company._my_approvals_digest_recipients()
        self.assertIn(self.test_user_1, recipients)
        self.test_user_1.email = False
        self.assertNotIn(
            self.test_user_1, self.company._my_approvals_digest_recipients()
        )

    def test_is_due(self):
        company = self.company
        self.assertFalse(company._my_approvals_digest_is_due(self._at(7)))
        self.assertTrue(company._my_approvals_digest_is_due(self._at(8)))
        company.my_approvals_digest_last_date = date(2026, 11, 6)
        self.assertFalse(company._my_approvals_digest_is_due(self._at(9)))
        company.my_approvals_digest_last_date = date(2026, 11, 5)
        self.assertTrue(company._my_approvals_digest_is_due(self._at(9)))
        company.my_approvals_digest_active = False
        self.assertFalse(company._my_approvals_digest_is_due(self._at(9)))

    def test_cron_sends_once_a_day(self):
        now = self._at(10)
        company_class = type(self.env["res.company"])
        with patch.object(
            company_class, "_my_approvals_digest_now", lambda _self: now
        ):
            self.env["res.company"]._cron_my_approvals_digest()
            self.assertEqual(self.company.my_approvals_digest_last_date, now.date())
            self.assertEqual(len(self._digest_mails(self.test_user_1)), 1)
            self.env["res.company"]._cron_my_approvals_digest()
        self.assertEqual(len(self._digest_mails(self.test_user_1)), 1)

    def test_cron_inactive(self):
        self.company.my_approvals_digest_active = False
        self.env["res.company"]._cron_my_approvals_digest()
        self.assertFalse(self._digest_mails(self.test_user_1))
