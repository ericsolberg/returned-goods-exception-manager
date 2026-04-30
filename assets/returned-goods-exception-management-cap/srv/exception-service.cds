using { returns.exceptions as db } from '../db/schema';

@path: '/exception'
@requires: ['internal-user', 'agent']
service ExceptionService {

  @readonly
  entity ReturnOrders as projection on db.ReturnOrders {
    *,
    status,
    expectedItems,
    receivedItems,
    auditHistory
  } actions {
    action confirm(reason : String);
    action escalate(reason : String not null);
    action resolve(decision : String not null, reason : String not null);
    action reject(reason : String not null);
    action linkOrder(linkedOrderId : String not null, reason : String);
    action retrySignal();
  };

  @readonly
  entity AuditHistory as projection on db.AuditHistory;

  @readonly
  entity ExpectedItems as projection on db.ExpectedItems;

  @readonly
  entity ReceivedItems as projection on db.ReceivedItems;

  @readonly
  entity ReturnOrderStatus as projection on db.ReturnOrderStatus;

  @readonly
  entity ChangeState as projection on db.ChangeState;
}
