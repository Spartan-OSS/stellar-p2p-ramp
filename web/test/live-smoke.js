// Opt-in live integration: disposable in-memory keys, never printed or persisted.
import {Keypair,TransactionBuilder,Networks} from '@stellar/stellar-sdk';
import assert from 'node:assert/strict';
import * as c from '../src/client.js';
const keys=Array.from({length:3},()=>Keypair.random());
for(const key of keys){const r=await fetch(`https://friendbot.stellar.org?addr=${key.publicKey()}`);if(!r.ok)throw new Error('Friendbot funding failed');}
const [seller,buyer,resolver]=keys.map(k=>k.publicKey());
const sign=async(xdr,source)=>{const tx=TransactionBuilder.fromXDR(xdr,Networks.TESTNET);tx.sign(keys.find(k=>k.publicKey()===source));return tx.toXDR();};
const transactions=[];const status=(message,hash)=>{if(hash&&!transactions.includes(hash)){transactions.push(hash);console.log(message);}};
await c.trust(buyer,seller,sign,status);
for(const refund of [false,true]){
 const id=await c.deploy(seller,buyer,resolver,sign,status);
 assert.equal((await c.inspect(seller,id)).state,'AwaitingFunding');
 await c.action(seller,id,'fund',sign,status);
 assert.equal((await c.inspect(seller,id)).state,'Funded');
 await c.action(buyer,id,'claim_payment',sign,status);
 if(refund){await c.action(buyer,id,'open_dispute',sign,status);await c.action(resolver,id,'resolve_seller',sign,status);}
 else await c.action(seller,id,'confirm_receipt',sign,status);
 const result=await c.inspect(seller,id);assert.equal(result.state,refund?'Refunded':'Released');
 console.log(JSON.stringify({contract:id,state:result.state,transactions}));
}
