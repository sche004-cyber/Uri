from common import *
for case in ("edit","delete_mid","reorder","truncate_last","insert"):
    m=new(); [m.create_milestone(f"MM-{i}","t") for i in range(4)]
    L=m.store.segment_path.read_bytes().splitlines(keepends=True)
    if case=="edit": L[1]=L[1].replace(b'"t"',b'"T"')
    elif case=="delete_mid": del L[1]
    elif case=="reorder": L[1],L[2]=L[2],L[1]
    elif case=="truncate_last": L=L[:-1]
    elif case=="insert": L.insert(2,L[1])
    m.store.segment_path.write_bytes(b"".join(L))
    v=m.store.verify(); print(case, v["ok"], (v["errors"] or ["-"])[0][:90])
    try: m.create_milestone("MM-X","x"); print("  write allowed!")
    except StoreError as e: print("  write refused", e.code)
