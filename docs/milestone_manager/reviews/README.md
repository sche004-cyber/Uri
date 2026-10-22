# Independent reviews of the Milestone Manager

Each round has a review record (`R<n>_<commit>.md`), a repair map (`R<n>_REPAIR.md`) and the reviewer's experiment
scripts (`R<n>_experiments/`).

**Warning about the experiment scripts.** They are preserved as historical evidence exactly as the reviewers wrote
them. Several contain hard-coded absolute paths to that reviewer's own temporary directory (for example
`C:/Users/cheta/AppData/Local/Temp/r12_lu6f27z2/...`) and some import source code from such a path. Before running
any of them, copy it into a fresh temporary directory and replace every absolute path
(`grep -n "AppData/Local/Temp" <script>`); otherwise it writes into another reviewer's folder or exercises an old
copy of the code (this happened once in review R13 and is recorded there).
