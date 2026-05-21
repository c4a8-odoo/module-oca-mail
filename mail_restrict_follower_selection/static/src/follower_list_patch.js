import { FollowerList } from "@mail/core/web/follower_list";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(FollowerList.prototype, {
    onClickAddFollowers() {
        const action = {
            type: "ir.actions.act_window",
            res_model: "mail.followers.edit",
            view_mode: "form",
            views: [[false, "form"]],
            name: _t("Add followers to this document"),
            target: "new",
            context: {
                default_res_model: this.props.thread.model,
                default_res_ids: [this.props.thread.id],
                dialog_size: "medium",
                form_view_ref: "mail.mail_followers_list_edit_form",
                // The web client filters the loadViews context down to
                // `lang` and keys ending with `_view_ref` (see
                // view_service.js). We smuggle the followed record's model
                // through under a `_view_ref`-suffixed key so the wizard's
                // `get_view` can apply the per-model follower domain, and
                // so each model gets its own cached arch entry.
                restrict_follower_res_model_view_ref: this.props.thread.model,
            },
        };
        this.action.doAction(action, {
            onClose: () => {
                this.props.onAddFollowers?.();
            },
        });
    },
});
