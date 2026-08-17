"""Tests for mail_activity_restrict."""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user


class TestMailActivityRestrict(TransactionCase):
    """Test the activity restriction on mail.activity."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.partner_model = cls.env["ir.model"]._get("res.partner")

        cls.activity_type_unrestricted = cls.env["mail.activity.type"].create(
            {
                "name": "Unrestricted Activity",
                "can_write_restrict": False,
            }
        )
        cls.activity_type_restricted = cls.env["mail.activity.type"].create(
            {
                "name": "Restricted Activity",
                "can_write_restrict": True,
            }
        )
        cls.user_assigned = new_test_user(
            cls.env,
            login="user_assigned@example.com",
            name="Assigned User",
            groups="base.group_user",
        )
        # Write access on res.partner makes core mail grant write on the
        # activities of that partner, so this user reaches an activity that
        # is not his own. Without it a test cannot tell this module and the
        # standard Odoo rules apart.
        cls.user_manager = new_test_user(
            cls.env,
            login="user_manager@example.com",
            name="Document Manager",
            groups="base.group_user,base.group_partner_manager",
        )
        cls.user_other = new_test_user(
            cls.env,
            login="user_other@example.com",
            name="Other User",
            groups="base.group_user",
        )

    @classmethod
    def _create_activity(cls, activity_type, user, env=None):
        return (env or cls.env)["mail.activity"].create(
            {
                "activity_type_id": activity_type.id,
                "res_model_id": cls.partner_model.id,
                "res_id": cls.partner.id,
                "user_id": user.id if user else False,
                "summary": activity_type.name,
                "date_deadline": "2026-12-31",
            }
        )

    def _can_write(self, activity, user):
        """Read can_write as ``user`` without hitting a cached value."""
        self.env.invalidate_all()
        return activity.with_user(user).can_write

    # ------------------------------------------------------------------
    # can_write: the restriction itself
    # ------------------------------------------------------------------

    def test_can_write_only_for_the_assigned_user(self):
        """Only the assignee keeps the buttons on a restricted activity."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        self.assertTrue(self._can_write(activity, self.user_assigned))
        self.assertFalse(self._can_write(activity, self.user_manager))

    def test_can_write_untouched_without_the_flag(self):
        """Counter test: the same user keeps the buttons without the flag."""
        activity = self._create_activity(
            self.activity_type_unrestricted, self.user_assigned
        )

        self.assertTrue(self._can_write(activity, self.user_assigned))
        self.assertTrue(self._can_write(activity, self.user_manager))

    def test_can_write_untouched_without_an_assignee(self):
        """An activity nobody is responsible for is not restricted.

        ``user_id`` is optional since 19.0. Hiding the buttons on an activity
        without an assignee would leave nobody able to handle it.
        """
        activity = self._create_activity(self.activity_type_restricted, False)
        self.assertFalse(activity.user_id)

        self.assertTrue(self._can_write(activity, self.user_manager))

    def test_can_write_stays_false_where_odoo_denies_it(self):
        """The restriction never widens what core allows."""
        activity = self._create_activity(
            self.activity_type_unrestricted, self.user_assigned
        )

        self.assertFalse(self._can_write(activity, self.user_other))

    def test_can_write_follows_the_assignee(self):
        """Handing the activity over moves the buttons along with it."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_manager
        )
        self.assertTrue(self._can_write(activity, self.user_manager))

        activity.with_user(self.user_manager).write({"user_id": self.user_assigned.id})

        self.assertFalse(self._can_write(activity, self.user_manager))
        self.assertTrue(self._can_write(activity, self.user_assigned))

    # ------------------------------------------------------------------
    # what the restriction deliberately does NOT do
    #
    # This module hides the buttons, it does not take access rights away.
    # The tests below pin that down, so nobody mistakes the restriction for
    # a permission later on.
    # ------------------------------------------------------------------

    def test_restriction_does_not_remove_write_access(self):
        """A user allowed by the standard rules can still write."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )
        self.assertFalse(self._can_write(activity, self.user_manager))

        activity.with_user(self.user_manager).write({"summary": "Still possible"})

        self.assertEqual(activity.summary, "Still possible")

    def test_restriction_does_not_remove_unlink_access(self):
        """A user allowed by the standard rules can still delete."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        activity.with_user(self.user_manager).unlink()

        self.assertFalse(activity.exists())

    def test_restriction_does_not_prevent_mark_done(self):
        """Marking as done is not blocked either, only hidden."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        activity.with_user(self.user_manager).action_done()

        self.assertEqual(activity.state, "done")

    def test_standard_rules_still_apply(self):
        """Users core denies stay denied."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        with self.assertRaises(AccessError):
            activity.with_user(self.user_other).write({"summary": "Nope"})

    # ------------------------------------------------------------------
    # the assigned user keeps working normally
    # ------------------------------------------------------------------

    def test_assigned_user_can_write(self):
        """The assignee edits a restricted activity."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        activity.with_user(self.user_assigned).write({"summary": "Updated"})

        self.assertEqual(activity.summary, "Updated")

    def test_assigned_user_can_mark_done(self):
        """The assignee completes a restricted activity."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        activity.with_user(self.user_assigned).action_done()

        self.assertEqual(activity.state, "done")

    def test_assigned_user_can_unlink(self):
        """The assignee deletes a restricted activity."""
        activity = self._create_activity(
            self.activity_type_restricted, self.user_assigned
        )

        activity.with_user(self.user_assigned).unlink()

        self.assertFalse(activity.exists())

    # ------------------------------------------------------------------
    # create: assigning somebody else must stay possible
    # ------------------------------------------------------------------

    def test_create_restricted_for_another_user(self):
        """Creating a restricted activity for somebody else is allowed."""
        activity = self._create_activity(
            self.activity_type_restricted,
            self.user_assigned,
            env=self.env(user=self.user_manager),
        )

        self.assertEqual(activity.user_id, self.user_assigned)

    def test_create_restricted_for_another_user_from_code(self):
        """activity_schedule() for somebody else is allowed.

        Restricted activity types are meant to be used as an approval step
        created from code, which assigns the approver rather than the caller.
        """
        activity = self.partner.with_user(self.user_manager).activity_schedule(
            activity_type_id=self.activity_type_restricted.id,
            user_id=self.user_assigned.id,
            summary="Approval",
        )

        self.assertEqual(activity.user_id, self.user_assigned)

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------

    def test_restrict_field_default_value(self):
        """The restriction flag defaults to False."""
        activity_type = self.env["mail.activity.type"].create(
            {
                "name": "Default Activity Type",
            }
        )

        self.assertFalse(activity_type.can_write_restrict)
