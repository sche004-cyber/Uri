# Evidence tools

Supported read-only preview: `serve_options.py` binds only 127.0.0.1:8137 and serves this documentation; it never starts URI services. `record_working_state.py --regression <log>` normalizes changed Dart line endings and records file hashes/results. `compare_final_references.py` computes current exact-hash regional comparisons. `compare_owner_reference.py` preserves the historical dashboard metric. `finalize_documents.py` refreshes final metadata; repeated invocation also appends the keyboard note, so review its changes.

Other scripts here preserve one-use editing/capture/report history. They are not idempotent migration commands and must not be blindly rerun. Product entry points are documented in HANDOFF.md. No tool in this folder grants integration/deployment authority.
