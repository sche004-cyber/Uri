D=/c/Users/cheta/AppData/Local/Temp/mmfb_wfnr98go
cd $D/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. TEMP=$(cygpath -w $D) TMP=$(cygpath -w $D)
mm(){ python -m scripts.dev_workflow.milestones --home $H --actor impl:a "$@" > $D/ex/last.out 2>&1; rc=$?; tr -d '\n' < $D/ex/last.out | cut -c1-260; echo "  -> exit $rc"; }
H=$D/ex/home_core
echo "## decisions never overwritten"
mm decision-add --id LDEC-901 --title t --decision original --date 2026-10-22 --evidence-class OTHER --source chat
mm decision-add --id LDEC-901 --title t2 --decision overwrite --date 2026-10-22 --evidence-class OTHER --source chat
mm decision-correct LDEC-901 --correction "fixed wording" --evidence-class OTHER --source chat
python -m scripts.dev_workflow.milestones --home $H show LDEC-901 | grep -E '"(decision|correction)"' 
echo "## LEDGER_LOSS_RECORDED after acknowledged truncation"
H=$D/ex/home_trunc
mm reanchor --reason "lost tail" --acknowledge-loss
mm milestone-update MM-A --objective "after loss"
grep -oE '[0-9a-f]{12}\.[0-9a-f]{6}' $D/ex/last.out | head -3
mm milestone-update MM-A --objective "after loss 2"
echo "## R23-03 resume bound with 64-char id"
H=$D/ex/home_r23; rm -rf $H; mm init --host-id hr
LONG=MM-$(python -c "print('A'*61)")
mm milestone-add $LONG --title "$(python -c "print('t'*300)")" --objective "$(python -c "print('o '*1500)")"
for n in 200 250 400; do python -m scripts.dev_workflow.milestones --home $H resume $LONG --max-chars $n --no-tasks > $D/ex/r.out; printf "max=%s len=%s\n" $n $(python -c "import sys;print(len(open(sys.argv[1],encoding='utf-8').read().rstrip(chr(10))))" $(cygpath -w $D/ex/r.out)); done
