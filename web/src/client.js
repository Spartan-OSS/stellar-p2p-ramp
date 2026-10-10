import {Address,Asset,Contract,Networks,Operation,TransactionBuilder,StrKey,rpc,nativeToScVal,scValToNative,xdr} from '@stellar/stellar-sdk';
export const WASM='7ca3481dd5b256c09011679c7089ccc4bbe5b4ef4b00abecf7a7f8811174b4df';
export const server=new rpc.Server('https://soroban-testnet.stellar.org');
export const assetFor=seller=>new Asset('DEMOUSD',seller);
export const validAddress=StrKey.isValidEd25519PublicKey;
const hex=s=>Uint8Array.from(s.match(/../g),b=>parseInt(b,16));
export async function submit(source,operation,sign,onStatus=()=>{},prepare=true){
 let tx=new TransactionBuilder(await server.getAccount(source),{fee:'10000',networkPassphrase:Networks.TESTNET}).addOperation(operation).setTimeout(180).build();
 if(prepare) tx=await server.prepareTransaction(tx);
 onStatus('Approve in your wallet');
 const signed=TransactionBuilder.fromXDR(await sign(tx.toXDR(),source),Networks.TESTNET);
 const sent=await server.sendTransaction(signed);
 if(!['PENDING','DUPLICATE'].includes(sent.status)) throw new Error(`Submission rejected: ${sent.status}`);
 onStatus(`Pending confirmation • ${sent.hash}`,sent.hash);
 for(let i=0;i<45;i++){
  const result=await server.getTransaction(sent.hash);
  if(result.status==='SUCCESS') {onStatus('Confirmed on Stellar testnet',sent.hash);return result;}
  if(result.status==='FAILED') throw new Error(`Transaction failed: ${sent.hash}`);
  await new Promise(r=>setTimeout(r,1500));
 }
 throw new Error(`Confirmation pending. Refresh state before retrying. Transaction: ${sent.hash}`);
}
export async function read(source,id,method){
 const tx=new TransactionBuilder(await server.getAccount(source),{fee:'100',networkPassphrase:Networks.TESTNET}).addOperation(new Contract(id).call(method)).setTimeout(60).build();
 const sim=await server.simulateTransaction(tx);
 if(!rpc.Api.isSimulationSuccess(sim)||!sim.result) throw new Error(sim.error||'Contract read failed');
 return scValToNative(sim.result.retval);
}
export async function inspect(source,id){
 const wasm=await server.getContractWasmByContractId(id);
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',wasm)),b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==WASM) throw new Error('Escrow code does not match the reviewed demo contract.');
 const terms=await read(source,id,'get_terms');
 if(terms.token!==assetFor(terms.seller).contractId(Networks.TESTNET)) throw new Error('This escrow does not use the seller-issued demo asset.');
 if(terms.amount!==100000000n||terms.ngn_kobo!==1500000n) throw new Error('This reviewer demo supports only 10 DEMOUSD / ₦15,000 escrows.');
 return {terms,state:(await read(source,id,'get_state'))[0]};
}
export async function deploy(seller,buyer,resolver,sign,status){
 const asset=assetFor(seller);
 // Asset contracts are deterministic; reuse when already deployed.
 const entries=await server.getLedgerEntries(new Contract(asset.contractId(Networks.TESTNET)).getFootprint());
 if(!entries.entries.length) await submit(seller,Operation.createStellarAssetContract({asset}),sign,status);
 const fields={amount:nativeToScVal(100000000n,{type:'i128'}),buyer:new Address(buyer).toScVal(),deadline:nativeToScVal(BigInt(Math.floor(Date.now()/1000)+3600),{type:'u64'}),ngn_kobo:nativeToScVal(1500000n,{type:'i128'}),reference:nativeToScVal(crypto.getRandomValues(new Uint8Array(32)),{type:'bytes'}),resolver:new Address(resolver).toScVal(),seller:new Address(seller).toScVal(),token:new Address(asset.contractId(Networks.TESTNET)).toScVal()};
 const result=await submit(seller,Operation.createCustomContract({address:new Address(seller),wasmHash:hex(WASM),salt:crypto.getRandomValues(new Uint8Array(32)),constructorArgs:[xdr.ScVal.scvMap(Object.entries(fields).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>new xdr.ScMapEntry({key:xdr.ScVal.scvSymbol(k),val:v})))]}),sign,status);
 return scValToNative(result.returnValue);
}
export async function action(source,id,name,sign,status){
 const args=name==='open_dispute'?[new Address(source).toScVal()]:name.startsWith('resolve_')?[nativeToScVal(name==='resolve_buyer')]:[];
 return submit(source,new Contract(id).call(name.startsWith('resolve_')?'resolve':name,...args),sign,status);
}
export const trust=(buyer,seller,sign,status)=>submit(buyer,Operation.changeTrust({asset:assetFor(seller)}),sign,status,false);
