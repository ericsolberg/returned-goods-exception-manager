using { cuid, managed, sap.common.CodeList } from '@sap/cds/common';

namespace returns.exceptions;

entity ReturnOrderStatus : CodeList {
  key code : String(30);
}

entity ReturnOrders : cuid, managed {
  externalOrderRef : String(50) not null;
  customerRef      : String(100);
  customerName     : String(60);
  companyCode          : String(4);
  distributionCenter   : String(4);
  receivedDate         : Date;
  status           : Association to ReturnOrderStatus;
  signalStatus     : String(20) default 'PENDING';
  linkedOrderId    : String(50);
  notes            : String(500);
  returnAmount     : Decimal(15,2);
  proposedClearing : Decimal(15,2);
  expectedItems    : Composition of many ExpectedItems  on expectedItems.order  = $self;
  receivedItems    : Composition of many ReceivedItems  on receivedItems.order  = $self;
  auditHistory     : Composition of many AuditHistory   on auditHistory.order   = $self;
}

entity ExpectedItems : cuid {
  order               : Association to ReturnOrders;
  materialId          : String(50);
  materialDescription : String(200);
  expectedQty         : Decimal(10,3);
  unit                : String(10);
  upcCode             : String(20);
  sku                 : String(50);
}

entity ReceivedItems : cuid {
  order               : Association to ReturnOrders;
  materialId          : String(50);
  materialDescription : String(200);
  receivedQty         : Decimal(10,3);
  unit                : String(10);
  condition           : String(50);
  upcCode             : String(20);
  sku                 : String(50);
}

entity AuditHistory : cuid, managed {
  order   : Association to ReturnOrders;
  action  : String(50) not null;
  reason  : String(500);
  userId  : String(200);
}

// Lightweight change marker — one row per watched entity set.
// Updated (outside the main transaction) after each successful IntakeService
// write so the UI can detect external mutations via smart polling.
entity ChangeState {
  key dataset       : String(50);
      lastChanged   : Timestamp;
      lastOperation : String(20);
}
