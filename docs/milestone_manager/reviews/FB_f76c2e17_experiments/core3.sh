D=/c/Users/cheta/AppData/Local/Temp/mmfb_wfnr98go
cd $D/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. TEMP=$(cygpath -w $D) TMP=$(cygpath -w $D)
mm(){ python -m scripts.dev_workflow.milestones --home $H --actor impl:a "$@" > $D/ex/last.out 2>&1; rc=$?; tr -d '\n' < $D/ex/last.out | cut -c1-260; echo "  -> exit $rc"; }
H=$D/ex/home_dec; rm -rf $H; mm init --host-id hd
echo "## decisions never overwritten"
mm decision-add --id LDEC-901 --title t --decision original --date 2026-10-22 --evidence-class OTHER --source chat
mm decision-add --id LDEC-901 --title t2 --decision overwrite --date 2026-10-22 --evidence-class OTHER --source chat
mm decision-correct LDEC-901 --correction "fixed wording" --evidence-class OTHER --source chat
python -m scripts.dev_workflow.milestones --home $H show LDEC-901 | grep -E 'original|overwrite|fixed wording'
echo "## anchors deleted -> record-then-refuse"
mm milestone-add MM-A --title A
cp -r $H $D/ex/home_anch; H=$D/ex/home_anch; rm $H/local/anchors.json
mm milestone-update MM-A --objective x
echo "ids in refusal: $(grep -cE '[0-9a-f]{12}\.[0-9a-f]{6}' $D/ex/last.out)"
mm milestone-update MM-A --objective x
mm status-set MM-A IN_PROGRESS --reason go
echo "## R23-03 resume bound with 64-char id"
H=$D/ex/home_r23; rm -rf $H; mm init --host-id hr
LONG=MM-$(python -c "print('A'*61)")
mm milestone-add $LONG --title "$(python -c "print('t'*190)")" --objective "$(python -c "print('o '*1900)")" --next-action "$(python -c "print('n '*1900)")"
for i in 1 2 3; do mm handoff $LONG --summary "$(python -c "print('h '*1900)")"; done
for n in 200 250 400; do python -m scripts.dev_workflow.milestones --home $H resume $LONG --max-chars $n --no-tasks > $D/ex/r.out; printf "max=%s len=%s\n" $n $(python -c "import sys;print(len(open(sys.argv[1],encoding='utf-8').read().rstrip(chr(10))))" $(cygpath -w $D/ex/r.out)); done
