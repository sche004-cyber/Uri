D=/c/Users/cheta/AppData/Local/Temp/mmfb_wfnr98go
cd $D/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. TEMP=$(cygpath -w $D) TMP=$(cygpath -w $D)
H=$D/ex/home_core; rm -rf $H
mm(){ python -m scripts.dev_workflow.milestones --home $H --actor impl:a "$@" > $D/ex/last.out 2>&1; rc=$?; tr -d '\n' < $D/ex/last.out | cut -c1-200; echo "  -> exit $rc"; }
C1=1111111111111111111111111111111111111111
P0=/d/uri-dev/uri-p0-audit
sha256sum $P0/decisions.md $P0/developmental.md > $D/ex/p0_before.txt
mm init --host-id hc
mm milestone-add MM-A --title A
mm status-set MM-A IN_PROGRESS --reason go
mm milestone-update MM-A --candidate-commit $C1
echo "## ACCEPTED without review"; mm status-set MM-A ACCEPTED --reason x
echo "## INTEGRATED from IN_PROGRESS"; mm status-set MM-A INTEGRATED --reason x
mm review-add MM-A --commit $C1 --reviewer-kind subagent --reviewer-id impl:a --assurance SUBAGENT --verdict ACCEPT --blocking-open 0 --findings-total 0 --result COMPLETED_WITH_RESULT --summary self
echo "## ACCEPTED with self review"; mm status-set MM-A ACCEPTED --reason x
mm review-add MM-A --commit $C1 --reviewer-kind subagent --reviewer-id sub:r --assurance SUBAGENT --verdict ACCEPT --blocking-open 0 --findings-total 0 --result COMPLETED_WITH_RESULT --summary ok
echo "## ACCEPTED ok"; mm status-set MM-A ACCEPTED --reason x
echo "## INTEGRATED without approval"; mm status-set MM-A INTEGRATED --reason x
echo "## candidate change locked"; mm milestone-update MM-A --candidate-commit 2222222222222222222222222222222222222222
echo "## decisions"; mm decision-add --id DEC-901 --title t --decision d --date 2026-10-22 --evidence-class OTHER --source chat
mm decision-add --id DEC-901 --title t2 --decision overwrite --date 2026-10-22 --evidence-class OTHER --source chat
python -m scripts.dev_workflow.milestones --home $H show DEC-901 2>/dev/null | grep -i '"decision"' | head -2
echo "## status --json keys"; python -m scripts.dev_workflow.milestones --home $H status --json --no-tasks > $D/ex/status.json; python -c "import json,sys;j=json.load(open(sys.argv[1]));print(sorted(j.keys()));m=j.get('milestones');print(type(m).__name__, (sorted(m[0].keys()) if isinstance(m,list) else sorted(list(m.values())[0].keys())))" $(cygpath -w $D/ex/status.json)
echo "## resume bounds"; for n in 0 50 200 300 1000; do python -m scripts.dev_workflow.milestones --home $H resume MM-A --max-chars $n --no-tasks > $D/ex/r.out; printf "max=%s len=%s\n" $n $(python -c "import sys;print(len(open(sys.argv[1],encoding='utf-8').read().rstrip('\n')))" $(cygpath -w $D/ex/r.out)); done
echo "## verify ok"; mm verify
echo "## crash: torn tail"; cp $H/events/hc.jsonl $D/ex/seg_backup; printf '{"v":1,"seg":"hc","seq":99' >> $H/events/hc.jsonl
mm milestone-update MM-A --objective "after torn"
mm recover --reason crash
ls $H/quarantine
mm milestone-update MM-A --objective "after recover"
echo "## tamper: flip a byte in event 2"; python - "$(cygpath -w $H/events/hc.jsonl)" <<'PY'
import sys
p=sys.argv[1]; b=open(p,'rb').read().split(b"\n")
b[1]=b[1].replace(b'"go"', b'"GO"'); open(p,'wb').write(b"\n".join(b))
PY
mm verify
mm status --no-tasks
mm milestone-update MM-A --objective "after tamper"
echo "## truncation (delete last line)"; H2=$D/ex/home_trunc; rm -rf $H2; cp -r $D/ex/home_core $H2; cp $D/ex/seg_backup $H2/events/hc.jsonl; python - "$(cygpath -w $H2/events/hc.jsonl)" <<'PY'
import sys
p=sys.argv[1]; b=open(p,'rb').read().rstrip(b"\n").split(b"\n"); open(p,'wb').write(b"\n".join(b[:-2])+b"\n")
PY
H=$H2; mm verify; mm milestone-update MM-A --objective "after trunc"; mm milestone-update MM-A --objective "after trunc retry"
echo "## status prints no conflict id"; python -m scripts.dev_workflow.milestones --home $H2 status --no-tasks | grep -cE '[0-9a-f]{12}\.[0-9a-f]{6}'
python -m scripts.dev_workflow.milestones --home $H2 status --json --no-tasks | grep -cE '[0-9a-f]{12}\.[0-9a-f]{6}'
python -m scripts.dev_workflow.milestones --home $H2 conflicts --entity LEDGER | grep -cE '[0-9a-f]{12}\.[0-9a-f]{6}'
echo "## importers (read-only P0)"; H=$D/ex/home_imp; rm -rf $H; mm init --host-id hi
mm import-decisions $P0/decisions.md
mm import-register $P0/developmental.md
mm import-decisions $P0/decisions.md
sha256sum $P0/decisions.md $P0/developmental.md > $D/ex/p0_after.txt; diff $D/ex/p0_before.txt $D/ex/p0_after.txt && echo P0_UNCHANGED
echo "## files in home (no cache)"; find $D/ex/home_core -type f | sed "s#$D/ex/##"
