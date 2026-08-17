When the activity type option "Restrict Write to Assigned User" on an activity type is enabled,
only the assigned user sees the buttons to edit, cancel or complete the activity.

The restriction is applied on the field Odoo uses to show those buttons, so it
does not get in the way of other modules working on activities.

This is a user interface restriction and not an access right. Users who may
change the activity through the standard Odoo rules can still do so elsewhere,
for example from the Activity Overview.

Activities without an assigned user are not restricted, otherwise nobody
could handle them anymore.
