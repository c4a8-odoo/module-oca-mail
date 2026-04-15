# Copyright 2018-22 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from collections import defaultdict

from odoo import api, fields, models, modules


class ResUsers(models.Model):
    _inherit = "res.users"

    activity_team_ids = fields.Many2many(
        comodel_name="mail.activity.team",
        relation="mail_activity_team_users_rel",
        string="Activity Teams",
    )

    @api.model
    def _get_activity_groups(self):
        if not self.env.context.get("team_activities"):
            return super()._get_activity_groups()

        search_limit = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("mail.activity.systray.limit", 1000)
        )
        activities = self.env["mail.activity"].search(
            [("team_id", "in", self.env.user.activity_team_ids.ids)],
            order="id desc",
            limit=search_limit,
        )

        user_company_ids = self.env.user.company_ids.ids
        is_all_user_companies_allowed = set(user_company_ids) == set(
            self.env.context.get("allowed_company_ids") or []
        )

        activities_model_groups = defaultdict(lambda: self.env["mail.activity"])
        activities_rec_groups = defaultdict(
            lambda: defaultdict(lambda: self.env["mail.activity"])
        )

        for activity in activities:
            if activity.res_model:
                activities_rec_groups[activity.res_model][activity.res_id] += activity
            else:
                activities_rec_groups["mail.activity"][activity.id] += activity

        model_activity_states = {
            "mail.activity": {
                "overdue_count": 0,
                "today_count": 0,
                "planned_count": 0,
                "total_count": 0,
            }
        }
        for model_name, activities_by_record in activities_rec_groups.items():
            res_ids = activities_by_record.keys()
            Model = self.env[model_name]
            has_model_access_right = Model.has_access("read")
            existing = Model.browse(res_ids).exists()
            if has_model_access_right:
                allowed_records = existing._filtered_access("read")
            else:
                allowed_records = Model
            unallowed_records = Model.browse(res_ids) - allowed_records
            if (
                has_model_access_right
                and unallowed_records
                and not is_all_user_companies_allowed
            ):
                unallowed_records -= (
                    (unallowed_records & existing)
                    .with_context(allowed_company_ids=user_company_ids)
                    ._filtered_access("read")
                )
            model_activity_states[model_name] = {
                "overdue_count": 0,
                "today_count": 0,
                "planned_count": 0,
                "total_count": 0,
            }
            for record_id, record_activities in activities_by_record.items():
                if record_id in unallowed_records.ids:
                    model_key = "mail.activity"
                    activities_model_groups["mail.activity"] += record_activities
                elif record_id in allowed_records.ids:
                    model_key = model_name
                    activities_model_groups[model_name] += record_activities
                elif record_id:
                    continue

                if "overdue" in record_activities.mapped("state"):
                    model_activity_states[model_key]["overdue_count"] += 1
                    model_activity_states[model_key]["total_count"] += 1
                elif "today" in record_activities.mapped("state"):
                    model_activity_states[model_key]["today_count"] += 1
                    model_activity_states[model_key]["total_count"] += 1
                else:
                    model_activity_states[model_key]["planned_count"] += 1

        model_ids = [
            self.env["ir.model"]._get_id(name) for name in activities_model_groups
        ]
        user_activities = {}
        for model_name, model_activities in activities_model_groups.items():
            Model = self.env[model_name]
            module = Model._original_module
            icon = module and modules.module.get_module_icon(module)
            model = self.env["ir.model"]._get(model_name).with_prefetch(model_ids)
            user_activities[model_name] = {
                "id": model.id,
                "name": (
                    model.name
                    if model_name != "mail.activity"
                    else self.env._("Other activities")
                ),
                "model": model_name,
                "type": "activity",
                "icon": icon,
                "domain": (
                    [("active", "in", [True, False])]
                    if model_name != "mail.activity" and "active" in Model
                    else []
                ),
                "total_count": model_activity_states[model_name]["total_count"],
                "today_count": model_activity_states[model_name]["today_count"],
                "overdue_count": model_activity_states[model_name]["overdue_count"],
                "planned_count": model_activity_states[model_name]["planned_count"],
                "view_type": getattr(Model, "_systray_view", "list"),
            }
            if model_name == "mail.activity":
                user_activities[model_name]["activity_ids"] = model_activities.ids
        return list(user_activities.values())
