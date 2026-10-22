from common import *
exec(open("r4_anchor.py").read().split("# (b)")[0].split("from common import *")[1])
def cs(label, mut):
    m = setup(); mut(m)
    v = m.store.verify(); p = m.projection()
    print(f"({label}) verify ok={v['ok']} errs={len(v['errors'])} warns={p['integrity_warnings'][:1]}")
    print("   no-ack:", tryre(m))
    print("   ack:", tryre(m, True)); after(m, "after ack")
def c(m):
    a = m.store.read_anchors(); trunc(m); a.pop("h1"); m.store.anchors_path.write_text(json.dumps(a))
def c2(m): trunc(m); m.store.anchors_path.write_text("{}")
def d(m):
    a = m.store.read_anchors(); trunc(m); a["h1"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
def e(m): trunc(m); m.store.anchors_path.unlink()
def garbage(m): trunc(m); m.store.anchors_path.write_text('{"h1": 5}')
def listy(m): trunc(m); m.store.anchors_path.write_text('[]')
def neg(m):
    a = m.store.read_anchors(); trunc(m); a["h1"]={"count":-1,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
def strc(m):
    a = m.store.read_anchors(); trunc(m); a["h1"]={"count":"3","head":a["h1"]["head"]}; m.store.anchors_path.write_text(json.dumps(a))
def nocount(m):
    a = m.store.read_anchors(); trunc(m); a["h1"]={"head":a["h1"]["head"]}; m.store.anchors_path.write_text(json.dumps(a))
def bighigh(m):
    a = m.store.read_anchors(); a["h1"]={"count":99,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
for l,f in [("c",c),("c2",c2),("d",d),("e",e),("garbage",garbage),("list",listy),("neg",neg),("strcount",strc),("nocount",nocount),("count99",bighigh)]:
    try: cs(l,f)
    except Exception as ex: print(f"({l}) EXC {type(ex).__name__}: {ex}")
