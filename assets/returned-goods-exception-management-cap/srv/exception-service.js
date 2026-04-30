'use strict';
const cds = require('@sap/cds');

// ─── Posting Agent Signal ────────────────────────────────────────────────────

async function signalPostingAgent(orderId, decision, linkedOrderId, userId) {
  const url = cds.env.requires?.postingAgent?.url;
  if (!url) throw new Error('postingAgent.url not configured');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orderId,
        decision,
        linkedOrderId: linkedOrderId || null,
        userId,
        timestamp: new Date().toISOString()
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Posting agent responded ${response.status}: ${text}`);
    }

    // Update signalStatus to SENT
    await UPDATE('returns.exceptions.ReturnOrders', orderId).with({ signalStatus: 'SENT' });
    console.log(`M5.achieved: journal entries posted [orderId=${orderId}]`);
  } finally {
    clearTimeout(timeout);
  }
}

// ─── Service Handler ─────────────────────────────────────────────────────────

module.exports = class ExceptionService extends cds.ApplicationService {

  async init() {
    const { ReturnOrders, AuditHistory } = this.entities;

    // ── confirm ──────────────────────────────────────────────────────────────
    this.on('confirm', ReturnOrders, async (req) => {
      const { ID } = req.params[0];
      const { reason } = req.data;

      const n = await UPDATE('returns.exceptions.ReturnOrders', ID)
        .where({ status_code: 'MATCHED' })
        .with({ status_code: 'RESOLVED_CONFIRMED' });

      if (!n) return req.reject(409, 'Action not allowed in current status');

      await INSERT.into('returns.exceptions.AuditHistory').entries({
        ID: cds.utils.uuid(),
        order_ID: ID,
        action: 'CONFIRMED',
        reason: reason || '',
        userId: req.user.id
      });

      try {
        await signalPostingAgent(ID, 'CONFIRMED', null, req.user.id);
        console.log(`M2.achieved: matched order confirmed and posting agent signalled [orderId=${ID}, userId=${req.user.id}]`);
      } catch (err) {
        await UPDATE('returns.exceptions.ReturnOrders', ID).with({ signalStatus: 'FAILED' });
        req.warn(503, `Decision saved, but posting agent signal failed: ${err.message}`);
        console.log(`M2.missed: confirmation submitted but posting agent signal failed [orderId=${ID}, error=${err.message}]`);
      }
    });

    // ── escalate ─────────────────────────────────────────────────────────────
    this.on('escalate', ReturnOrders, async (req) => {
      const { ID } = req.params[0];
      const { reason } = req.data;

      const n = await UPDATE('returns.exceptions.ReturnOrders', ID)
        .where({ status_code: 'MATCHED' })
        .with({ status_code: 'PARTIAL' });

      if (!n) return req.reject(409, 'Action not allowed in current status');

      await INSERT.into('returns.exceptions.AuditHistory').entries({
        ID: cds.utils.uuid(),
        order_ID: ID,
        action: 'ESCALATED',
        reason: reason || '',
        userId: req.user.id
      });

      console.log(`M3.achieved: order escalated to partial [orderId=${ID}]`);
    });

    // ── resolve ───────────────────────────────────────────────────────────────
    this.on('resolve', ReturnOrders, async (req) => {
      const { ID } = req.params[0];
      const { decision, reason } = req.data;

      if (!['ACCEPT', 'REJECT'].includes(decision)) {
        return req.reject(400, 'decision must be ACCEPT or REJECT');
      }

      const targetStatus = decision === 'ACCEPT' ? 'RESOLVED_CONFIRMED' : 'RESOLVED_REJECTED';
      const auditAction  = decision === 'ACCEPT' ? 'RESOLVED_ACCEPTED'  : 'RESOLVED_REJECTED';

      const n = await UPDATE('returns.exceptions.ReturnOrders', ID)
        .where({ status_code: 'PARTIAL' })
        .with({ status_code: targetStatus });

      if (!n) return req.reject(409, 'Action not allowed in current status');

      await INSERT.into('returns.exceptions.AuditHistory').entries({
        ID: cds.utils.uuid(),
        order_ID: ID,
        action: auditAction,
        reason: reason || '',
        userId: req.user.id
      });

      try {
        await signalPostingAgent(ID, decision === 'ACCEPT' ? 'ACCEPTED' : 'REJECTED', null, req.user.id);
        console.log(`M3.achieved: partial order resolved [orderId=${ID}, decision=${decision}, userId=${req.user.id}]`);
      } catch (err) {
        await UPDATE('returns.exceptions.ReturnOrders', ID).with({ signalStatus: 'FAILED' });
        req.warn(503, `Decision saved, but posting agent signal failed: ${err.message}`);
        console.log(`M3.missed: partial order resolution failed [orderId=${ID}, reason=${err.message}]`);
      }
    });

    // ── reject ────────────────────────────────────────────────────────────────
    this.on('reject', ReturnOrders, async (req) => {
      const { ID } = req.params[0];
      const { reason } = req.data;

      // Read original status first (for correct milestone log)
      const row = await SELECT.one.from('returns.exceptions.ReturnOrders').where({ ID }).columns('status_code');
      const originalStatus = row?.status_code;

      const n = await UPDATE('returns.exceptions.ReturnOrders', ID)
        .where({ status_code: { in: ['UNMATCHED', 'PARTIAL'] } })
        .with({ status_code: 'RESOLVED_REJECTED' });

      if (!n) return req.reject(409, 'Action not allowed in current status');

      await INSERT.into('returns.exceptions.AuditHistory').entries({
        ID: cds.utils.uuid(),
        order_ID: ID,
        action: 'REJECTED',
        reason: reason || '',
        userId: req.user.id
      });

      try {
        await signalPostingAgent(ID, 'REJECTED', null, req.user.id);
        if (originalStatus === 'UNMATCHED') {
          console.log(`M4.achieved: unmatched order manually resolved [orderId=${ID}, linkedOrderId=null, userId=${req.user.id}]`);
        } else {
          console.log(`M3.achieved: partial order resolved [orderId=${ID}, decision=REJECT, userId=${req.user.id}]`);
        }
      } catch (err) {
        await UPDATE('returns.exceptions.ReturnOrders', ID).with({ signalStatus: 'FAILED' });
        req.warn(503, `Decision saved, but posting agent signal failed: ${err.message}`);
        console.log(`M4.missed: unmatched order resolution failed [orderId=${ID}, reason=${err.message}]`);
      }
    });

    // ── linkOrder ─────────────────────────────────────────────────────────────
    this.on('linkOrder', ReturnOrders, async (req) => {
      const { ID } = req.params[0];
      const { linkedOrderId, reason } = req.data;

      const n = await UPDATE('returns.exceptions.ReturnOrders', ID)
        .where({ status_code: 'UNMATCHED' })
        .with({ status_code: 'RESOLVED_LINKED', linkedOrderId });

      if (!n) return req.reject(409, 'Action not allowed in current status');

      await INSERT.into('returns.exceptions.AuditHistory').entries({
        ID: cds.utils.uuid(),
        order_ID: ID,
        action: 'RESOLVED_LINKED',
        reason: reason || '',
        userId: req.user.id
      });

      try {
        await signalPostingAgent(ID, 'LINKED', linkedOrderId, req.user.id);
        console.log(`M4.achieved: unmatched order manually resolved [orderId=${ID}, linkedOrderId=${linkedOrderId}, userId=${req.user.id}]`);
      } catch (err) {
        await UPDATE('returns.exceptions.ReturnOrders', ID).with({ signalStatus: 'FAILED' });
        req.warn(503, `Decision saved, but posting agent signal failed: ${err.message}`);
        console.log(`M4.missed: unmatched order resolution failed [orderId=${ID}, reason=${err.message}]`);
      }
    });

    // ── retrySignal ───────────────────────────────────────────────────────────
    this.on('retrySignal', ReturnOrders, async (req) => {
      const { ID } = req.params[0];

      const [row] = await SELECT.from('returns.exceptions.ReturnOrders')
        .where({ ID })
        .columns('signalStatus', 'status_code', 'linkedOrderId', 'createdBy');

      if (!row) return req.reject(404, 'Order not found');
      if (row.signalStatus !== 'FAILED') {
        return req.reject(409, 'Signal retry only allowed when signalStatus is FAILED');
      }

      // Derive decision from status
      const decisionMap = {
        RESOLVED_CONFIRMED: 'CONFIRMED',
        RESOLVED_REJECTED:  'REJECTED',
        RESOLVED_LINKED:    'LINKED'
      };
      const decision = decisionMap[row.status_code] || 'CONFIRMED';

      try {
        await signalPostingAgent(ID, decision, row.linkedOrderId, req.user.id);
        console.log(`M5.achieved: journal entries posted [orderId=${ID}]`);
      } catch (err) {
        req.warn(503, `Retry failed: ${err.message}`);
        console.log(`M5.missed: posting agent reported failure or no confirmation received [orderId=${ID}]`);
      }
    });

    await super.init();
  }
};
