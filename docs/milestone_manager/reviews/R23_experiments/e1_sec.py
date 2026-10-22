from common import *
AWS="AKIA"+"ABCDEFGHIJKLMNOP"; GH="ghp_"+"c"*36; PW="password=Hunter2Hunter2"
res=[]
# store API reanchor / recover
for kw in ({"reason":"r "+AWS},{"actor":GH},{"session":"xoxb-1234567890abc"},{"reason":PW},{"actor":"a"*201}):
    m=new(); m.create_milestone("MM-A","A"); b=segbytes(m.home); a=dict(actor="impl:a",reason="x",session=None); a.update(kw)
    try: m.store.reanchor(a["actor"],a["reason"],a["session"],acknowledge_loss=True); r="WROTE"
    except StoreError as e: r=e.code
    res.append(("reanchor",list(kw)[0],r,segbytes(m.home)==b))
for kw in ({"actor":AWS},{"session":GH},{"actor":"x"*300}):
    m=new(); m.create_milestone("MM-A","A")
    with m.store.segment_path.open("ab") as f: f.write(b'{"torn":')
    b=segbytes(m.home); a=dict(actor="impl:a",session=None); a.update(kw)
    try: m.store.recover(a["actor"],a["session"]); r="WROTE"
    except StoreError as e: r=e.code
    res.append(("recover",list(kw)[0],r,segbytes(m.home)==b, not (m.home/"quarantine").exists()))
# CLI reanchor/recover
for argv in (["--actor","impl:a","reanchor","--reason",PW,"--acknowledge-loss"],["--actor",AWS,"reanchor","--reason","x"],
             ["--actor","impl:a","--session",GH,"reanchor","--reason","x"],
             ["--actor","impl:a","recover","--reason","tok "+GH],["--actor","impl:a","--session",AWS,"recover"],
             ["--actor","impl:a","recover","--reason","token: abcd1234efgh"]):
    m=new(); m.create_milestone("MM-A","A")
    with m.store.segment_path.open("ab") as f: f.write(b'{"torn":')
    b=segbytes(m.home); rc,out=runcli("--home",str(m.home),*argv)
    res.append(("cli",argv[-3:] if "recover" not in argv else argv, rc, segbytes(m.home)==b, json.loads(out).get("error") or json.loads(out).get("refused")))
for r in res: print(r)
