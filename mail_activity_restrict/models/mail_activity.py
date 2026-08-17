"""Reserve the activity actions for the assigned user."""

from odoo import api, models


class MailActivity(models.Model):
    """Hide the activity actions from everybody but the assigned user."""

    _inherit = "mail.activity"

    def _get_can_write_restrict_activities(self):
        """Return the activities the restriction applies to.

        Reads are done with sudo so that the restriction does not depend on
        the current user being able to read the activity type.

        Activities without an assigned user are skipped: ``user_id`` is
        optional since 19.0, and hiding the actions on an activity nobody is
        responsible for would leave it without any way to be handled. Modules
        introducing another kind of responsible extend this method (see
        ``mail_activity_team_restrict``).
        """
        restricted = self.sudo().filtered(
            lambda activity: activity.activity_type_id.can_write_restrict
            and activity.user_id
        )
        return self.browse(restricted.ids)

    def _get_can_write_restrict_allowed_activities(self):
        """Return restricted activities the current user may act on."""
        return self.sudo().filtered_domain([("user_id", "=", self.env.uid)])

    @api.depends(
        "res_model", "res_id", "user_id", "activity_type_id.can_write_restrict"
    )
    def _compute_can_write(self):
        """Clear ``can_write`` for everybody but the assigned user.

        Core uses ``can_write`` to show or hide the edit, cancel and mark done
        buttons of an activity. Applying the restriction here instead of in
        ``_check_access`` keeps this module out of the way of every other
        addon that writes on activities: access rights are left untouched, so
        nothing that Odoo or another module does on an activity can fail
        because of this module.

        The flip side is that this is a user interface restriction and not an
        access right. A user allowed to modify the activity by the standard
        rules keeps that permission, for instance from the Activity Overview.
        """
        super()._compute_can_write()
        restricted = self._get_can_write_restrict_activities()
        if not restricted:
            return
        for activity in (
            restricted - restricted._get_can_write_restrict_allowed_activities()
        ):
            activity.can_write = False
