import json, pathlib, sys
root=pathlib.Path(r'C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent')
sys.path.insert(0,str(root))
from uri_supervisor_bridge.qualification import build_record, record_digest, validate_shape, revalidate
from uri_core.client_runtime.harness import probe_version
exe=sys.executable
version=probe_version([exe])['version']
evidence=pathlib.Path(__file__).with_name('qualification_evidence.txt')
evidence.write_text('original evidence',encoding='utf-8')
record=build_record(provider='fixture',level='FIXTURE_ONLY',spec_id='generic_ndjson',executable=exe,
                    executable_args=[],version=version,models=['model_a'],evidence_path=evidence,qualified_by='probe')
print('original',record['provider'],record['models'],bool(revalidate(record,allow_fixture=True)))
evidence.write_text('replaced evidence',encoding='utf-8')
print('replaced_evidence_still_revalidates',bool(revalidate(record,allow_fixture=True)))
altered=dict(record,models=['model_b'],qualified_by='forged')
altered['record_sha256']=record_digest(altered)
print('modified_with_recomputed_digest',altered['provider'],altered['models'],bool(validate_shape(altered)),bool(revalidate(altered,allow_fixture=True)))
print('record_has_client_binding',any('client' in k for k in record))
print('record_has_provider_evidence_binding',record['evidence_sha256'],record['provider'])
