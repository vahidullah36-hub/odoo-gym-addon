/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { onWillUnmount } from "@odoo/owl";

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        
        // Sadece Spor Salonu Ziyaretleri modelindeysek calissin
        if (this.props.resModel === 'gym.visit') {
            this.gymRefreshInterval = setInterval(() => {
                if (document.hidden || this.editedRecord) {
                    return;
                }

                // Odoo 18 icin en guvenli yenileme yontemi: dogrudan veri modelini tazele.
                if (this.model && this.model.root && typeof this.model.root.load === 'function') {
                    this.model.root.load();
                } else if (this.model && typeof this.model.load === 'function') {
                    this.model.load();
                }

            }, 5000);

            // Ekrandan cikildiginda sayaci temizle.
            onWillUnmount(() => {
                if (this.gymRefreshInterval) {
                    clearInterval(this.gymRefreshInterval);
                }
            });
        }
    }
});
