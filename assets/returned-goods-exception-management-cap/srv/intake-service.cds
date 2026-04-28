using { returns.exceptions as db } from '../db/schema';

@path: '/intake'
service IntakeService {

  @(restrict: [
    { grant: 'READ',   to: ['internal-user', 'agent'] },
    { grant: 'CREATE', to: ['internal-user', 'agent'] },
    { grant: 'UPDATE', to: ['internal-user', 'agent'] }
  ])
  entity ReturnOrders as projection on db.ReturnOrders {
    *,
    expectedItems,
    receivedItems
  };

  @(restrict: [{ grant: 'CREATE', to: ['internal-user', 'agent'] }])
  entity ExpectedItems as projection on db.ExpectedItems;

  @(restrict: [{ grant: 'CREATE', to: ['internal-user', 'agent'] }])
  entity ReceivedItems as projection on db.ReceivedItems;
}
