import test from 'node:test';
import assert from 'node:assert/strict';
import {allowed,advance,validateParticipants} from '../src/flow.js';
test('buyer cannot release and resolver cannot release undisputed funds',()=>{
 assert.deepEqual(allowed('PaymentClaimed','buyer'),['open_dispute']);
 assert.throws(()=>advance('Funded','resolver','resolve_buyer'));
});
test('release workflow and disputed refund',()=>{
 let s=advance('AwaitingFunding','seller','fund');s=advance(s,'buyer','claim_payment');
 assert.equal(advance(s,'seller','confirm_receipt'),'Released');
 s=advance(s,'buyer','open_dispute');assert.equal(advance(s,'resolver','resolve_seller'),'Refunded');
});
test('terminal states reject all actions',()=>{
 for(const s of ['Released','Refunded']) for(const r of ['buyer','seller','resolver']) assert.deepEqual(allowed(s,r),[]);
});
test('distinct valid participants required',()=>{
 assert.throws(()=>validateParticipants('a','a','c',()=>true));
 assert.throws(()=>validateParticipants('a','b','c',()=>false));
});
