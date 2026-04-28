'use strict';
const cds = require('@sap/cds');
const { expect } = cds.test(__dirname + '/..');

// Seed a minimal ReturnOrder directly to the DB, bypassing service restrictions
async function seedOrder(statusCode) {
  const id = cds.utils.uuid();
  await INSERT.into('returns.exceptions.ReturnOrders').entries({
    ID: id,
    externalOrderRef: `SO-TEST-${id.slice(0, 8)}`,
    status_code: statusCode,
    signalStatus: 'PENDING'
  });
  return id;
}

describe('ExceptionService — custom action handlers', () => {
  let srv;

  beforeAll(async () => {
    srv = await cds.connect.to('ExceptionService');
  });

  // ── confirm ────────────────────────────────────────────────────────────────

  it('confirm transitions MATCHED → RESOLVED_CONFIRMED', async () => {
    const id = await seedOrder('MATCHED');

    await srv.send({ event: 'confirm', entity: 'ReturnOrders', params: [{ ID: id }], data: {} });

    const [row] = await SELECT.from('returns.exceptions.ReturnOrders').where({ ID: id }).columns('status_code');
    expect(row.status_code).to.equal('RESOLVED_CONFIRMED');

    const history = await SELECT.from('returns.exceptions.AuditHistory').where({ order_ID: id });
    expect(history).to.have.length(1);
    expect(history[0].action).to.equal('CONFIRMED');
  });

  it('confirm on UNMATCHED order is rejected with 409', async () => {
    const id = await seedOrder('UNMATCHED');
    try {
      await srv.send({ event: 'confirm', entity: 'ReturnOrders', params: [{ ID: id }], data: {} });
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err.status ?? err.statusCode ?? err.code).to.equal(409);
    }
  });

  // ── escalate ───────────────────────────────────────────────────────────────

  it('escalate transitions MATCHED → AMBIGUOUS', async () => {
    const id = await seedOrder('MATCHED');

    await srv.send({ event: 'escalate', entity: 'ReturnOrders', params: [{ ID: id }], data: { reason: 'Qty mismatch' } });

    const [row] = await SELECT.from('returns.exceptions.ReturnOrders').where({ ID: id }).columns('status_code');
    expect(row.status_code).to.equal('AMBIGUOUS');
  });

  // ── resolve ────────────────────────────────────────────────────────────────

  it('resolve ACCEPT transitions AMBIGUOUS → RESOLVED_CONFIRMED', async () => {
    const id = await seedOrder('AMBIGUOUS');

    await srv.send({ event: 'resolve', entity: 'ReturnOrders', params: [{ ID: id }], data: { decision: 'ACCEPT', reason: 'Verified' } });

    const [row] = await SELECT.from('returns.exceptions.ReturnOrders').where({ ID: id }).columns('status_code');
    expect(row.status_code).to.equal('RESOLVED_CONFIRMED');
  });

  it('resolve with invalid decision is rejected with 400', async () => {
    const id = await seedOrder('AMBIGUOUS');
    try {
      await srv.send({ event: 'resolve', entity: 'ReturnOrders', params: [{ ID: id }], data: { decision: 'MAYBE', reason: 'Test' } });
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err.status ?? err.statusCode ?? err.code).to.equal(400);
    }
  });

  // ── linkOrder ──────────────────────────────────────────────────────────────

  it('linkOrder transitions UNMATCHED → RESOLVED_LINKED and stores linkedOrderId', async () => {
    const id = await seedOrder('UNMATCHED');

    await srv.send({ event: 'linkOrder', entity: 'ReturnOrders', params: [{ ID: id }], data: { linkedOrderId: 'SO-2024-99999' } });

    const [row] = await SELECT.from('returns.exceptions.ReturnOrders').where({ ID: id }).columns('status_code', 'linkedOrderId');
    expect(row.status_code).to.equal('RESOLVED_LINKED');
    expect(row.linkedOrderId).to.equal('SO-2024-99999');
  });

  // ── reject ─────────────────────────────────────────────────────────────────

  it('reject transitions UNMATCHED → RESOLVED_REJECTED', async () => {
    const id = await seedOrder('UNMATCHED');

    await srv.send({ event: 'reject', entity: 'ReturnOrders', params: [{ ID: id }], data: { reason: 'Cannot identify order' } });

    const [row] = await SELECT.from('returns.exceptions.ReturnOrders').where({ ID: id }).columns('status_code');
    expect(row.status_code).to.equal('RESOLVED_REJECTED');
  });
});

describe('IntakeService — CREATE validation', () => {
  let intake;

  beforeAll(async () => {
    intake = await cds.connect.to('IntakeService');
  });

  it('rejects CREATE without externalOrderRef with 400', async () => {
    try {
      await intake.send('CREATE', 'ReturnOrders', { status_code: 'MATCHED' });
      expect.fail('Should have thrown');
    } catch (err) {
      expect(err.status ?? err.statusCode ?? err.code).to.equal(400);
    }
  });
});
