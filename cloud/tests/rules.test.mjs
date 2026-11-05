import {readFileSync} from 'node:fs';
import {after, before, test} from 'node:test';
import {initializeTestEnvironment, assertFails, assertSucceeds} from '@firebase/rules-unit-testing';
import {doc, getDoc, setDoc, deleteDoc, getDocs, collection} from 'firebase/firestore';
let env;
before(async()=>{env=await initializeTestEnvironment({projectId:'demo-ymir-sync',firestore:{rules:readFileSync('firestore.rules','utf8')}});});
after(async()=>{await env?.cleanup();});
test('owner can create and read own state',async()=>{
 const db=env.authenticatedContext('alice').firestore(),ref=doc(db,'users/alice/sync/state');
 await assertSucceeds(setDoc(ref,{schema:1,payload:'{"p:default":{"id":"default"}}'}));await assertSucceeds(getDoc(ref));
});
test('anonymous and other accounts cannot read or write state',async()=>{
 for(const db of [env.unauthenticatedContext().firestore(),env.authenticatedContext('bob').firestore()]){
  const ref=doc(db,'users/alice/sync/state');await assertFails(getDoc(ref));await assertFails(setDoc(ref,{schema:1,payload:'{}'}));
 }
});
test('owner cannot list users, delete state, add fields or bypass size/schema',async()=>{
 const db=env.authenticatedContext('alice').firestore(),ref=doc(db,'users/alice/sync/state');
 await assertFails(getDocs(collection(db,'users/alice/sync')));await assertFails(deleteDoc(ref));
 for(const data of [{schema:2,payload:'{}'},{schema:1,payload:{}},{schema:1,payload:'{}',admin:true},{schema:1,payload:'x'.repeat(850001)}])await assertFails(setDoc(ref,data));
});
test('all unrelated documents denied',async()=>{await assertFails(setDoc(doc(env.authenticatedContext('alice').firestore(),'users/alice/other/data'),{schema:1,payload:'{}'}));});
