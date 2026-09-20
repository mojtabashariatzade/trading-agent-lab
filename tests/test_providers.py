import unittest
from agentops.providers import Cursor, GitHub, ProviderError, Http
from tests.fakes import HEAD, REPO


class StubHttp:
    def __init__(self,responses): self.responses=list(responses); self.calls=[]
    def call(self,*args):
        self.calls.append(args)
        response=self.responses.pop(0)
        if isinstance(response,Exception): raise response
        return response


class ProviderTests(unittest.TestCase):
    def test_cursor_v1_payload(self):
        c=Cursor('test'); c.http=StubHttp([{'run':{'id':'run-1'}}]); c.create('bc-test','DEV','https://github.com/'+REPO,HEAD,'task')
        method,path,payload=c.http.calls[0]
        self.assertEqual((method,path),('POST','/v1/agents')); self.assertFalse(payload['workOnCurrentBranch']); self.assertNotIn('envVars',payload); self.assertEqual(payload['agentId'],'bc-test')
    def test_cursor_conflict_recovers_existing_run(self):
        c=Cursor('test'); c.http=StubHttp([ProviderError('Cursor',409),{'latestRunId':'old-run'}]); self.assertEqual(c.create('bc-test','DEV','https://github.com/'+REPO,HEAD,'task'),'old-run')
    def test_review_no_pr(self):
        c=Cursor('test'); c.http=StubHttp([{'run':{'id':'r'}}]); c.create('bc-test','QA','https://github.com/'+REPO,HEAD,'task',review=True); self.assertFalse(c.http.calls[0][2]['autoCreatePR'])
    def test_http_rejects_arbitrary_url(self):
        h=Http('https://api.github.com',{},'GitHub')
        with self.assertRaises(ValueError): h.call('GET','https://evil.example/')
    def test_merge_binds_sha(self):
        g=GitHub(REPO,'test'); g.http=StubHttp([{'merged':True}]); g.merge(7,HEAD); self.assertEqual(g.http.calls[0][2]['sha'],HEAD)
    def test_ci_no_run_waits(self):
        g=GitHub(REPO,'test'); g.http=StubHttp([{'workflow_runs':[]}]); self.assertEqual(g.ci(HEAD)[0],'WAIT')
    def test_ci_skipped_job_not_pass(self):
        g=GitHub(REPO,'test'); r={'id':1,'head_sha':HEAD,'event':'pull_request','head_repository':{'full_name':REPO},'html_url':'test','status':'completed','conclusion':'success'}; g.http=StubHttp([{'workflow_runs':[r]},{'jobs':[{'name':'qa','conclusion':'skipped'}]}]); self.assertEqual(g.ci(HEAD)[0],'FAIL')
    def test_ci_exact_workflow_run(self):
        g=GitHub(REPO,'test'); r={'id':1,'head_sha':HEAD,'event':'pull_request','head_repository':{'full_name':REPO},'html_url':'test','status':'completed','conclusion':'success'}; g.http=StubHttp([{'workflow_runs':[r]},{'jobs':[{'name':'qa','conclusion':'success'}]}]); self.assertEqual(g.ci(HEAD)[0],'PASS')
    def test_newer_ci_failure_overrides_old_success(self):
        g=GitHub(REPO,'test'); r={'id':1,'head_sha':HEAD,'event':'pull_request','head_repository':{'full_name':REPO},'html_url':'test','status':'completed','conclusion':'success'}; r2=dict(r,id=2,conclusion='failure'); g.http=StubHttp([{'workflow_runs':[r,r2]}]); self.assertEqual(g.ci(HEAD)[0],'FAIL')
