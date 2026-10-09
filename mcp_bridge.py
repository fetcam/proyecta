#!/usr/bin/env python3
"""Local MCP stdio bridge. Pin the project and source profile at startup."""
import argparse
import json
import sys
from app import Store, data_home


def serve(store, pid, aid, writable=False):
    tools=[{'name':'project_context','description':'Estado maestro y rol asignado a esta fuente.',
            'inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
           {'name':'preview_summary','description':'Revisa qué estado y decisiones puede incorporar este perfil.',
            'inputSchema':{'type':'object','properties':{'summary':{'type':'object'}},'required':['summary'],'additionalProperties':False}}]
    if writable:
        tools.append({'name':'apply_summary','description':'Incorpora exclusivamente elementos seleccionados. Usa versión y digests de preview_summary. Respeta autorizaciones del usuario.',
            'inputSchema':{'type':'object','properties':{'summary':{'type':'object'},'version':{'type':'integer'},'selected':{'type':'array','items':{'type':'string'}}},'required':['summary','version','selected'],'additionalProperties':False}})
    for line in sys.stdin:
        req=None
        try:
            req=json.loads(line)
            if not isinstance(req,dict): raise ValueError('JSON-RPC inválido.')
            if 'id' not in req: continue
            method=req.get('method'); params=req.get('params',{})
            if method=='initialize':
                requested=params.get('protocolVersion','2024-11-05')
                supported=('2024-11-05','2025-03-26','2025-06-18')
                result={'protocolVersion':requested if requested in supported else supported[0],'capabilities':{'tools':{}},'serverInfo':{'name':'proyecta','version':'1.1.0'}}
            elif method=='ping': result={}
            elif method=='tools/list': result={'tools':tools}
            elif method=='tools/call':
                name=params.get('name'); args=params.get('arguments',{})
                try:
                    if name=='project_context': value=store.exchange_prompt(pid,aid)
                    elif name=='preview_summary': value=store.preview_exchange({'project_id':pid,'account_id':aid,'summary':args.get('summary')})
                    elif name=='apply_summary' and writable:
                        snapshot=store.apply_exchange({'project_id':pid,'account_id':aid,'summary':args.get('summary'),'version':args.get('version'),'selected':args.get('selected')})
                        value={'project':next(p for p in snapshot['projects'] if p['id']==pid),'result':'Selección incorporada; no se importaron conversaciones.'}
                    else: raise ValueError('Herramienta no disponible.')
                    result={'content':[{'type':'text','text':value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)}]}
                except (ValueError,RuntimeError,KeyError,TypeError) as e:
                    result={'isError':True,'content':[{'type':'text','text':str(e)}]}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':req['id'],'error':{'code':-32601,'message':'Método no disponible.'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result},ensure_ascii=False),flush=True)
        except Exception as e:
            print(json.dumps({'jsonrpc':'2.0','id':req.get('id') if isinstance(req,dict) else None,'error':{'code':-32600,'message':str(e)}}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Puente MCP local de Proyecta para Claude Code y Codex')
    parser.add_argument('--project',type=int,required=True)
    parser.add_argument('--account',type=int,required=True)
    parser.add_argument('--data-dir',type=str,default=str(data_home()))
    parser.add_argument('--allow-write',action='store_true')
    options=parser.parse_args()
    from pathlib import Path
    serve(Store(Path(options.data_dir)/'proyecta.sqlite3'),options.project,options.account,options.allow_write)
