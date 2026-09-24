"""Offline security/contract tests. HTTP test uses loopback; external APIs are fakes."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib import request, error
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2] / 'deploy/n8n'

def chmod_mode_probe(base: Path) -> int:
    probe = base / '.chmod-probe'
    probe.mkdir()
    os.chmod(probe, 0o700)
    return probe.stat().st_mode & 0o777

def load(name):
    spec=importlib.util.spec_from_file_location('n8n_'+name,ROOT/(name+'.py'))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

gateway, installer, remote=load('gateway'), load('install'), load('remote_install')


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.calls=[]
        self.conf={'telegram_owner_id':42,'telegram_chat_id':42,'telegram_bot_token':'test-only-not-a-real-token'}
        self.b=gateway.Bridge(Path(self.tmp.name),self.conf,self.api)
    def tearDown(self): self.tmp.cleanup()
    def api(self,url,payload=None,headers=None):
        self.calls.append((url,payload))
        if url.endswith('/getMe'): return {'ok':True,'result':{'id':88}}
        if url.endswith('/getWebhookInfo'): return {'ok':True,'result':{'url':''}}
        if url.endswith('/getUpdates'): return {'ok':True,'result':[]}
        return {'ok':True,'result':{'message_id':1}}
    def message(self,text='/status',ident=1,owner=42,chat=42,age=0):
        return {'update_id':ident,'message':{'text':text,'date':int(time.time())-age,
                'from':{'id':owner,'is_bot':False},'chat':{'id':chat,'type':'private'}}}
    def count(self,table):
        with self.b.db() as db:return db.execute('SELECT count(*) FROM '+table).fetchone()[0]
    def test_default_is_inert(self):
        self.assertEqual(self.b.sync()['state'],'DISABLED')
        self.assertEqual(self.b.poll()['state'],'DISABLED')
        self.assertEqual(self.b.deliver()['state'],'DISABLED')
        self.assertEqual(self.calls,[])
    def test_auth_allows_only_owner_private_chat(self):
        self.b.ingest(self.message(owner=43));self.b.ingest(self.message(ident=2,chat=43))
        self.assertEqual(self.count('inbox'),0)
    def test_old_commands_do_not_resume(self):
        self.b.ingest(self.message('/resume',age=2000))
        self.assertTrue(self.b.get('paused',True));self.assertEqual(self.count('outbox'),0)
    def test_duplicate_update_one_reply(self):
        msg=self.message(); self.b.ingest(msg);self.b.ingest(msg)
        self.assertEqual(self.count('outbox'),1);self.assertEqual(self.b.get('telegram_offset'),2)
    def test_offsets_never_regress(self):
        self.b.ingest(self.message(ident=10));self.b.ingest(self.message(ident=2))
        self.assertEqual(self.b.get('telegram_offset'),11)
    def test_secret_never_stored_in_inbox_or_job(self):
        secret='github_pat_'+'X'*30
        self.b.ingest(self.message('token='+secret))
        with self.b.db() as db: rows=[r[0] for r in db.execute('SELECT body FROM inbox')]
        self.assertNotIn(secret,str(rows));self.assertEqual(self.count('jobs'),0)
    def test_natural_text_is_private_request_not_execution(self):
        self.b.ingest(self.message('Review the data gate'))
        self.assertEqual(self.count('jobs'),1);self.assertEqual(self.calls,[])
        self.assertEqual(self.b.claim({'executor':'worker'})['state'],'BLOCKED')
    def test_pause_and_resume_do_not_enable_trading(self):
        self.b.ingest(self.message('/resume'));self.assertFalse(self.b.get('paused'))
        self.assertFalse(self.b.status()['trading_enabled'])
        self.b.ingest(self.message('/pause',ident=2));self.assertTrue(self.b.get('paused'))
    def test_no_fake_immediate_ai_answer(self):
        self.assertEqual(self.b.status()['ai_executor'],'EXTERNAL_WORKER_REQUIRED')
    def test_handoff_required_before_any_poll(self):
        self.conf['telegram_polling_enabled']=True
        with self.assertRaises(RuntimeError):self.b.poll()
        self.assertEqual(self.calls,[])
    def enable_poll(self):
        self.conf.update(telegram_polling_enabled=True,telegram_handoff={
            'old_consumer_stopped':True,'verified_by':'test-operator','verified_at':'2026-09-22T00:00:00Z','bot_id':88})
    def test_webhook_never_deleted(self):
        self.enable_poll()
        old=self.b.transport
        self.b.transport=lambda url,payload=None,headers=None: {'ok':True,'result':{'url':'https://existing.example'}} if url.endswith('/getWebhookInfo') else old(url,payload,headers)
        with self.assertRaises(RuntimeError):self.b.poll()
        self.assertFalse(any('deleteWebhook' in u for u,p in self.calls))
    def test_wrong_bot_handoff_rejected(self):
        self.enable_poll();self.conf['telegram_handoff']['bot_id']=99
        with self.assertRaises(RuntimeError):self.b.poll()
    def test_valid_poll_bounded(self):
        self.enable_poll();self.assertEqual(self.b.poll()['state'],'POLL_COMPLETE')
        self.assertEqual(len(self.calls),3)
    def test_one_poll_consumer(self):
        self.enable_poll();self.b.poll_lock.acquire()
        try:self.assertEqual(self.b.poll()['state'],'BUSY')
        finally:self.b.poll_lock.release()
    def test_daily_digest_dedupes(self):
        self.b.digest();self.b.digest();self.assertEqual(self.count('outbox'),1)
    def test_delivery_uncertainty_not_retried(self):
        self.conf['telegram_sending_enabled']=True;self.b.digest()
        self.b.transport=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('timeout'))
        with self.assertRaises(RuntimeError):self.b.deliver()
        self.assertEqual(self.b.deliver()['state'],'EMPTY')
        self.assertEqual(self.b.status()['delivery_uncertain'],1)
    def test_restart_preserves_inbox(self):
        self.b.ingest(self.message('hello'))
        other=gateway.Bridge(Path(self.tmp.name),self.conf,self.api)
        self.assertEqual(other.get('telegram_offset'),2)
    def test_claim_requires_named_worker_and_one_job(self):
        self.conf['worker_handoff_enabled']=True
        self.b.ingest(self.message('/resume'));self.b.ingest(self.message('work',ident=2))
        job=self.b.claim({'executor':'test-worker'})
        self.assertEqual(job['state'],'CLAIMED')
        self.assertEqual(self.b.claim({'executor':'other'})['state'],'BLOCKED')
    def test_worker_result_not_automatic_done(self):
        self.conf['worker_handoff_enabled']=True
        self.b.ingest(self.message('/resume'));self.b.ingest(self.message('work',ident=2))
        job=self.b.claim({'executor':'test-worker'})
        result=self.b.result({**job,'summary':'Tests submitted','evidence_url':'https://github.com/mojtabashariatzade/trading-agent-lab/pull/1'})
        self.assertEqual(result['state'],'RESULT_SUBMITTED')
        self.assertIn('NOT_DONE',result['verification'])
    def test_worker_cannot_submit_external_evidence(self):
        with self.assertRaises(ValueError): self.b.result({'summary':'safe','evidence_url':'https://evil.example'})
    def test_api_does_not_follow_arbitrary_repo(self):
        with self.assertRaises(ValueError): self.b.github('/repos/other/repo/issues')
    def test_empty_snapshot_truthfully_stale(self): self.assertTrue(self.b.status()['stale'])
    def test_unknown_command_never_executes(self):
        self.b.ingest(self.message('/approve T006 whatever'));self.assertEqual(self.count('jobs'),0)
    def test_loopback_auth_and_worker_key_separation(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),gateway.make_handler(self.b,'control','worker'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        root='http://127.0.0.1:'+str(server.server_port)
        try:
            for path,key in [('/v1/status',''),('/v1/jobs/claim','control')]:
                req=request.Request(root+path,data=b'{}',headers={'X-Control-Key':key})
                with self.assertRaises(error.HTTPError) as exc:request.urlopen(req)
                self.assertEqual(exc.exception.code,401)
            req=request.Request(root+'/v1/status',data=b'{}',headers={'X-Control-Key':'control'})
            with request.urlopen(req) as resp:self.assertFalse(json.load(resp)['trading_enabled'])
        finally:server.shutdown();server.server_close();thread.join()


class PackageTests(unittest.TestCase):
    def test_workflows_inactive_and_fixed_urls(self):
        flows=json.loads((ROOT/'workflows.json').read_text())
        self.assertEqual({f['id'] for f in flows},set(installer.IDS))
        for f in flows:
            self.assertFalse(f['active'])
            self.assertEqual(f['nodes'][1]['parameters']['url'].split('/v1')[0],'http://bridge:8080')
    def test_only_loopback_port_exposed(self):
        services=json.loads((ROOT/'compose.json').read_text())['services']
        self.assertEqual(services['n8n']['ports'],['127.0.0.1:5678:5678'])
        self.assertNotIn('ports',services['db']);self.assertNotIn('ports',services['bridge'])
        self.assertNotIn('docker.sock',json.dumps(services))
    def test_no_n8n_broker_or_github_tokens(self):
        n=json.loads((ROOT/'compose.json').read_text())['services']['n8n']
        self.assertNotIn('connections',n['secrets']);self.assertNotIn('worker_key',n['secrets'])
    def test_prepare_preserves_keys_and_disables_integrations(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self.assertIn('NO_SERVICES',installer.prepare('owner@example.test',root))
            before=(root/'.private/encryption').read_text()
            self.assertIn('PRESERVED',installer.prepare('owner@example.test',root))
            self.assertEqual(before,(root/'.private/encryption').read_text())
            cfg=json.loads((root/'.private/connections').read_text())
            self.assertFalse(cfg['telegram_polling_enabled']);self.assertFalse(cfg['worker_handoff_enabled'])
            observed_mode=(root/'.private').stat().st_mode & 0o777
            probe_mode=chmod_mode_probe(root)
            if probe_mode==0o700:
                self.assertEqual(observed_mode,0o700)
            else:
                self.assertEqual(observed_mode,probe_mode)
    def test_prepare_will_not_overwrite_unmarked_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'.private').mkdir()
            with self.assertRaises(RuntimeError):installer.prepare('owner@example.test',root)
    def test_old_review_rejected(self):
        from datetime import date
        with self.assertRaises(ValueError):installer.assert_review(date(2025,1,1))
    def test_shell_injection_targets_rejected(self):
        for host in ['-oProxyCommand=bad','host; touch x','example.com/../../','$(bad)']:
            with self.assertRaises(ValueError):remote.host_target(host,'root')
        self.assertEqual(remote.host_target('192.0.2.4','ubuntu'),'ubuntu@192.0.2.4')
    def test_package_upload_excludes_private_files(self):
        self.assertNotIn('.private',str(remote.FILES)); self.assertNotIn('secrets',str(remote.FILES))
    def test_docker_bootstrap_refuses_to_remove_existing_packages(self):
        text=(ROOT/'bootstrap-ubuntu.sh').read_text()
        self.assertNotIn('apt remove',text);self.assertNotIn('usermod',text)
        self.assertIn('--fresh-server-approved',text)

if __name__=='__main__':unittest.main()
