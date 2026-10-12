import json,os,sys,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from uri_core.core.runtime_identity import child_environment
state=root/"work/c1"/("regression_"+uuid.uuid4().hex)
for rel in ["uri_workspace","home/roaming","home/local","temp"]:(state/rel).mkdir(parents=True,exist_ok=True)
(state/"uri_workspace/capabilities_registry.json").write_bytes((root/"uri_workspace/capabilities_registry.json").read_bytes())
env=child_environment(state,Path(sys.executable))
os.environ.clear();os.environ.update(env)
os.chdir(state)
import shutil
shutil.copytree(root/"uri_core",state/"uri_core",ignore=shutil.ignore_patterns("__pycache__"))
import pytest
files=["test_m22_3_route_authorization.py","test_m22_3_bind_refusal.py","test_m22_3_cors.py","test_m22_3_rate_limiting.py","test_m22_3_ask_size_limit.py","test_m22_2_roles_sessions.py","test_auth_session.py","test_m22_4_capability_resolver.py","test_m22_4_grant_endpoints.py","test_capability_authority_boundary.py","test_graph_authority_boundary.py","test_experience_tier_never_authorizes.py","test_approval_gate.py","test_approval_store.py","test_server_approval_endpoints.py","test_approval_resumption.py","test_canonical_execution.py","test_arn_1_deterministic_narrowing.py","test_graphify_index.py","test_startup_services.py","test_server_user_scoped_startup.py","test_portable_paths.py"]
args=["-q","--disable-warnings","-p","no:cacheprovider","--junitxml="+str(root/"work/c1/regression.xml")]+[str(root/f) for f in files]
code=pytest.main(args)
(root/"work/c1/regression-run.json").write_text(json.dumps({"files":files,"synthetic_root":str(state),"returncode":code}))
sys.exit(code)

