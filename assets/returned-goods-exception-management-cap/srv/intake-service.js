'use strict';
const cds = require('@sap/cds');

// Updates the ChangeState marker for ReturnOrders after the transaction commits.
// Called from after-handlers so the DB write only happens when the main operation
// succeeded — req.on('succeeded', ...) fires post-commit.
function _updateChangeMarker(op, req) {
  req.on('succeeded', async () => {
    const now = new Date().toISOString();
    try {
      const n = await cds.db.run(
        UPDATE('returns.exceptions.ChangeState')
          .where({ dataset: 'ReturnOrders' })
          .with({ lastChanged: now, lastOperation: op })
      );
      if (!n) {
        await cds.db.run(
          INSERT.into('returns.exceptions.ChangeState')
            .entries({ dataset: 'ReturnOrders', lastChanged: now, lastOperation: op })
        );
      }
      console.log(`[ChangeMarker] updated [op=${op}, ts=${now}]`);
    } catch (err) {
      console.error(`[ChangeMarker] update failed [op=${op}]:`, err.message);
    }
  });
}

module.exports = class IntakeService extends cds.ApplicationService {

  async init() {
    const { ReturnOrders } = this.entities;

    this.before('CREATE', ReturnOrders, (req) => {
      if (!req.data.externalOrderRef) {
        console.log(`M1.missed: return order exception missing required field [field=externalOrderRef]`);
        return req.reject(400, 'externalOrderRef is required');
      }
    });

    this.after('CREATE', ReturnOrders, (data, req) => {
      console.log(`M1.achieved: return order exception received [orderId=${data.ID}, status=${data.status_code}]`);
      _updateChangeMarker('CREATE', req);
    });

    this.after('UPDATE', ReturnOrders, (data, req) => {
      _updateChangeMarker('UPDATE', req);
    });

    await super.init();
  }
};

