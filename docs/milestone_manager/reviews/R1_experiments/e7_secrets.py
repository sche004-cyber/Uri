from common import *
cases = {
 "stripe live": "key sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc" + "AbCdEf",
 "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
 "password no digit": "password: correcthorsebatterystaple",
 "token= generic": "token=9f8e7d6c5b4a39281706f5e4d3c2b1a0",
 "hf token": "hf_" + "AbCdEfGhIjKlMnOpQrStUvWxYz012345",
 "basic auth url": "https://user:S3cretPassw0rd@example.com/repo.git",
 "client_secret": "client_secret=AbCd1234EfGh5678",
 "anthropic in quotes": "ANTHROPIC_API_KEY='sk-ant-api03-" + "x"*30 + "'",
}
for k,v in cases.items(): print(f"{k:22} detected={model.find_secret(v)}")
fp = ["See docs/password-reset-flow2.md", "the api_key: env-var-NAME1 is documented", "pwd=D:/uri-dev/worktree1", "secret: s3cret-sauce-recipe"]
for v in fp: print(f"FP? {v!r:45} -> {model.find_secret(v)}")
