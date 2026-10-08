cd /c/Users/cheta/.codex/worktrees/uri-phase2a/uri-agent
OUT=../evidence/phase2c/collect_bisect.log; : > $OUT
for f in test_*.py step*_test.py; do
  s=$(date +%s)
  timeout 40 .venv/Scripts/python.exe -I -m pytest --collect-only -q -p no:cacheprovider "$f" > /dev/null 2>&1; rc=$?
  echo "$rc $(( $(date +%s) - s ))s $f" >> $OUT
done
echo "BISECT_DONE" >> $OUT
