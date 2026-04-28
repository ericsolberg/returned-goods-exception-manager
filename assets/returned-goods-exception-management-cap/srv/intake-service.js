'use strict';
const cds = require('@sap/cds');

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
    });

    await super.init();
  }
};
