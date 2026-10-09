// Optional DOM integration test: npm install jsdom in an isolated test environment.
// These tests do not validate browser rendering or responsive layout.
const { JSDOM, VirtualConsole } = require('jsdom');
const { spawn } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const assert = require('node:assert/strict');
const app=resolve(__dirname,'../app.py');
const dir=mkdtempSync(join(tmpdir(),'proyecta-ui-'));
const child=spawn(process.env.PYTHON||'python3',[app,'--no-browser','--port','0','--data-dir',dir]);
let dom;
const wait=async test=>{for(let i=0;i<100;i++){if(test())return;await new Promise(r=>setTimeout(r,30));}throw Error('No se cumplió condición de interfaz')};
function click(doc,selector){const e=doc.querySelector(selector);assert.ok(e,selector);e.click();}
function fill(doc,name,value){const e=doc.querySelector(`[name="${name}"]`);assert.ok(e,name);if(e.type==='checkbox')e.checked=value;else e.value=value;}
(async()=>{
 const base=await new Promise((resolve,reject)=>{let out='';child.stdout.on('data',data=>{out+=data;const m=out.match(/http:\/\/127\.0\.0\.1:\d+/);if(m)resolve(m[0])});child.on('error',reject);child.on('exit',code=>reject(Error('El servidor se detuvo: '+code)));setTimeout(()=>reject(Error('Inicio agotó tiempo')),5000).unref()});
 const errors=[];
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 dom=await JSDOM.fromURL(base,{runScripts:'dangerously',resources:'usable',virtualConsole:vc,beforeParse(window){window.fetch=(path,options)=>fetch(new URL(path,base),options);window.scrollTo=()=>{};window.confirm=()=>true;window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};window.navigator.clipboard={writeText:async()=>{}};}});
 const w=dom.window,d=w.document;
 const submit=()=>d.querySelector('#editor-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await wait(()=>d.querySelector('#seed'));
 click(d,'#seed');await wait(()=>d.querySelectorAll('.card').length===4);
 assert.match(d.querySelector('.notice').textContent,/demostración/);
 click(d,'[data-new-project]');fill(d,'name','Proyecta');fill(d,'goal','Estado compartido entre herramientas.');fill(d,'next_action','Instalar en Linux Mint.');submit();
 await wait(()=>d.querySelectorAll('.card').length===5&&!d.querySelector('#editor').open);
 const open=[...d.querySelectorAll('.card')].find(c=>c.textContent.includes('Proyecta')).querySelector('[data-open]');open.click();
 click(d,'[data-project-add]');fill(d,'title','Validar instalación');fill(d,'needs_me',true);submit();
 await wait(()=>d.querySelector('[data-edit-task]')&&!d.querySelector('#editor').open);
 click(d,'[data-edit-task]');fill(d,'status','completada');submit();
 await wait(()=>d.querySelector('#form-error').textContent.includes('Registra evidencia'));
 fill(d,'evidence','API y flujo DOM verificados en Linux de ejecución.');submit();
 await wait(()=>!d.querySelector('#editor').open);assert.match(d.querySelector('.row').textContent,/Completada/);
 click(d,'[data-tab="decisions"]');click(d,'[data-project-add]');fill(d,'text','Linux Mint primero, formatos portables.');submit();
 await wait(()=>!d.querySelector('#editor').open);assert.match(d.querySelector('.row').textContent,/formatos portables/);
 click(d,'[data-context]');await wait(()=>d.querySelector('#context-preview')?.textContent.includes('Linux Mint primero'));
 d.querySelector('#ask-question').value='¿Qué sigue?';d.querySelector('#ask-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await wait(()=>d.querySelector('#ask-answer').textContent.includes('Instalar en Linux Mint.'));
 click(d,'[data-view="attention"]');assert.ok(!d.querySelector('#content').textContent.includes('Validar instalación'));
 click(d,'[data-view="portfolio"]');click(d,'[data-new-project]');fill(d,'name','<img src=x onerror=alert(1)>');submit();
 await wait(()=>d.querySelectorAll('.card').length===6);assert.equal(d.querySelectorAll('.card img').length,0);
 const search=d.querySelector('#search');search.value='Cognitia';search.dispatchEvent(new w.Event('input',{bubbles:true}));assert.equal(d.querySelectorAll('.card').length,1);
 assert.deepEqual(errors,[]);
 console.log('PASS: flujos DOM de alta/edición, evidencia, decisiones, contexto, consulta, atención, escape de HTML y búsqueda.');
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{dom?.window.close();child.kill('SIGTERM');child.on('close',()=>rmSync(dir,{recursive:true,force:true}));});
