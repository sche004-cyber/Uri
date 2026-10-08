import hashlib,json,pathlib,sqlite3
ev=pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d')
for tag in ('codex_composition4','claude_composition1'):
    d=json.loads((ev/(tag+'.json')).read_text(encoding='utf-8'))
    print(tag,'code',d.get('run',{}).get('final_code'),'qualification',d.get('qualification_decision'))
    p=d.get('direct_probe',{})
    stdout=ev/(tag+'_stdout.txt')
    if stdout.exists(): print('stdout sha',hashlib.sha256(stdout.read_bytes()).hexdigest(),'claimed',p.get('stdout_sha256'))
    db=pathlib.Path(d['base'])/'client/control/supervisor/ledger.db'
    if db.exists():
        con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
        try:
            print('db integrity',con.execute('pragma integrity_check').fetchone()[0])
            for table in ('task','attempt','authorization','completion_record'):
                print(table,'rows',con.execute('select count(*) from '+table).fetchone()[0])
            a=con.execute('select argv_sha256,exit_code,session_id from attempt').fetchall()
            print('db attempts',a,'claimed',[(x['argv_sha256'],x['exit_code'],x['session_id']) for x in d.get('run',{}).get('ledger',{}).get('attempts',[])])
        finally:con.close()
