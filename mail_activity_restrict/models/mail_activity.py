"""Restrict mail.activity modifications to the assigned user."""

from odoo import models
from odoo.exceptions import AccessError

# Context key set by write() to flag a write that only touches technical
# fields, i.e. one that is not the user acting on the activity. It is always
# set explicitly there, so a client-supplied context value cannot be used to
# bypass the restriction.
TECHNICAL_WRITE_KEY = "mail_activity_restrict_technical_write"


class MailActivity(models.Model):
    """Extend mail.activity access checks for restricted activity types."""

    _inherit = "mail.activity"

    def _get_can_write_restrict_fields(self):
        """Return the fields whose modification counts as acting on the activity.

        Other addons write bookkeeping fields on activities while acting on
        behalf of the user, and core calls them in the middle of its own
        operations. ``mail_activity_reminder`` for instance stamps
        ``last_reminder_local`` from ``action_notify()``, which
        ``mail.activity.create()`` calls whenever an activity is created for
        somebody other than its creator. Such a write is not the user acting
        on the activity, so restricting it would make this module break any
        addon that touches an activity in passing.
        """
        return {
            "active",
            "activity_type_id",
            "attachment_ids",
            "automated",
            "date_deadline",
            "date_done",
            "feedback",
            "note",
            "res_id",
            "res_model_id",
            "summary",
            "user_id",
        }

    def _get_can_write_restrict_activities(self):
        """Return the activities the restriction applies to.

        Reads are done with sudo because this runs inside
        :meth:`_check_access`, which has to return an access error instead of
        raising one.

        Activities without an assigned user are skipped: ``user_id`` is
        optional since 19.0, and restricting them would leave an activity that
        nobody can ever modify again, not even to assign somebody to it.
        Modules introducing another kind of responsible extend this method
        (see ``mail_activity_team_restrict``).
        """
        restricted = self.sudo().filtered(
            lambda activity: activity.activity_type_id.can_write_restrict
            and activity.user_id
        )
        return self.browse(restricted.ids)

    def _get_can_write_restrict_allowed_activities(self):
        """Return restricted activities the current user may modify."""
        return self.sudo().filtered_domain([("user_id", "=", self.env.uid)])

    def _make_can_write_restrict_error(self, operation: str) -> AccessError:
        """Build the access error raised for restricted activity types."""
        if len(self) == 1:
            return AccessError(
                self.env._(
                    "You cannot %(operation)s this activity because only "
                    "the assigned user can modify activities of this type.",
                    operation=operation,
                )
            )
        return AccessError(
            self.env._(
                "You cannot %(operation)s some activities because only their "
                "assigned user can modify activities of this type.",
                operation=operation,
            )
        )

    def write(self, vals):
        """Flag writes that do not touch what the user actually acts on."""
        technical = not (set(vals) & self._get_can_write_restrict_fields())
        records = self.with_context(**{TECHNICAL_WRITE_KEY: technical})
        return super(MailActivity, records).write(vals)

    def unlink(self):
        """Deleting an activity is always the user acting on it."""
        records = self.with_context(**{TECHNICAL_WRITE_KEY: False})
        return super(MailActivity, records).unlink()

    def _check_access(self, operation: str) -> tuple | None:
        """Restrict write-like operations when the activity type requires it."""
        result = super()._check_access(operation)
        if operation not in ("write", "unlink") or not self or self.env.su:
            return result
        if operation == "write" and self.env.context.get(TECHNICAL_WRITE_KEY):
            return result

        restricted = self._get_can_write_restrict_activities()
        forbidden = restricted - restricted._get_can_write_restrict_allowed_activities()
        if not forbidden:
            return result

        if result and not (forbidden - result[0]):
            return result

        forbidden = result[0] | forbidden if result else forbidden
        return forbidden, lambda: forbidden._make_can_write_restrict_error(operation)
