export const STATES = ['AwaitingFunding','Funded','PaymentClaimed','Disputed','Released','Refunded'];
export function allowed(state, role) {
  if(state==='AwaitingFunding') return role==='seller'?['fund']:[];
  if(state==='Funded') return role==='buyer'?['claim_payment','open_dispute']:role==='seller'?['open_dispute']:[];
  if(state==='PaymentClaimed') return role==='seller'?['confirm_receipt','open_dispute']:role==='buyer'?['open_dispute']:[];
  if(state==='Disputed') return role==='resolver'?['resolve_buyer','resolve_seller']:[];
  return [];
}
export function advance(state, role, action) {
  if(!allowed(state,role).includes(action)) throw new Error('This role cannot perform that action in the current state.');
  return ({fund:'Funded',claim_payment:'PaymentClaimed',confirm_receipt:'Released',open_dispute:'Disputed',resolve_buyer:'Released',resolve_seller:'Refunded'})[action];
}
export const short = a => a ? `${a.slice(0,6)}…${a.slice(-5)}` : 'Not connected';
export function validateParticipants(seller,buyer,resolver,valid) {
  if(![seller,buyer,resolver].every(valid)) throw new Error('Use three valid Stellar G-account addresses.');
  if(new Set([seller,buyer,resolver]).size!==3) throw new Error('Seller, buyer and resolver must be different accounts.');
}
