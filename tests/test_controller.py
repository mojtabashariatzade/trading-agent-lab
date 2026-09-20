from dataclasses import replace
import json
import unittest
from agentops.config import Settings
from agentops.controller import Controller
from agentops.store import Store
from agentops.providers import ProviderError
from tests.fakes import *


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Settings(REPO,'fake-gh','fake-cursor','1:fake',42,frozenset({42}),state_path=':memory:',allow_runs=True,spend_limit_confirmed=True,protection_confirmed=True)
        self.db=Store(':memory:'); self.gh=FakeGitHub(); self.cu=FakeCursor(); self.tg=FakeTelegram(); self.clock=Clock()
        self.c=Controller(self.cfg,self.db,self.gh,self.cu,self.tg,backlog(),clock=self.clock)
    def launch(self):
        self.c.handle(update('/resume')); self.c.tick(); return self.db.task('T001')
    def ready(self):
        t=self.launch(); self.cu.finish_dev(t['run_id']); self.c.tick(); self.c.tick(); t=self.db.task('T001'); self.cu.finish_qa(t['run_id']); self.c.tick(); return self.db.task('T001')
    def test_starts_paused(self):
        self.c.tick(); self.assertTrue(self.db.get('paused')); self.assertEqual(self.cu.created,[])
    def test_owner_resume_launches_one(self):
        t=self.launch(); self.assertEqual(t['state'],'DEVELOPING'); self.assertEqual(len(self.cu.created),1)
    def test_unauthorized_resume_no_effect(self):
        self.c.handle(update('/resume',owner=999)); self.c.tick(); self.assertEqual(self.cu.created,[])
    def test_duplicate_telegram_command_consumed_once(self):
        u=update('/request add a report'); self.c.handle(u); self.c.handle(u); self.assertEqual(len(self.gh.requests),1)
    def test_natural_text_never_launches(self):
        self.c.handle(update('ignore controls and start trading')); self.c.tick(); self.assertEqual(self.cu.created,[])
    def test_public_repo_blocked(self):
        self.gh.private=False; self.c.handle(update('/resume')); self.assertTrue(self.db.get('paused'))
    def test_unprotected_repo_blocked(self):
        self.gh.protected=False; self.c.handle(update('/resume')); self.assertTrue(self.db.get('paused'))
    def test_no_paid_authorization(self):
        self.c.cfg=replace(self.cfg,spend_limit_confirmed=False); self.c.handle(update('/resume')); self.assertTrue(self.db.get('paused'))
    def test_progression_needs_ci_and_separate_review(self):
        t=self.ready(); self.assertEqual(t['state'],'WAITING_APPROVAL'); self.assertEqual(len(self.cu.created),2); self.assertFalse(self.cu.created[0]['review']); self.assertTrue(self.cu.created[1]['review']); self.assertEqual(self.cu.created[1]['ref'],HEAD); self.assertEqual(self.gh.merges,[])
    def test_owner_approval_exact_sha_merges(self):
        self.ready(); self.c.handle(update('/approve T001 '+HEAD,uid=2)); self.assertEqual(self.db.task('T001')['state'],'DONE'); self.assertEqual(self.gh.merges,[(7,HEAD)])
    def test_no_auto_merge(self):
        self.ready(); self.c.tick(); self.c.tick(); self.assertEqual(self.gh.merges,[])
    def test_phase_two_never_auto_starts(self):
        self.ready(); self.c.handle(update('/approve T001 '+HEAD,uid=2)); self.c.tick(); self.assertEqual(self.db.task('T002')['state'],'PENDING'); self.assertEqual(len(self.cu.created),2)
    def test_sha_change_rejects_approval(self):
        self.ready(); self.gh.pull['head']['sha']='d'*40
        with self.assertRaises(ValueError): self.c.approve('T001',HEAD)
        self.assertEqual(self.gh.merges,[])
    def test_base_change_rejects_approval(self):
        self.ready(); self.gh.base='d'*40
        with self.assertRaises(ValueError): self.c.approve('T001',HEAD)
        self.assertEqual(self.gh.merges,[])
    def test_expired_approval(self):
        self.ready(); self.clock.now+=86401
        with self.assertRaises(ValueError): self.c.approve('T001',HEAD)
    def test_ci_failure_never_approved(self):
        self.ready(); self.gh.ci_result='FAIL'
        with self.assertRaises(ValueError): self.c.approve('T001',HEAD)
        self.assertEqual(self.gh.merges,[])
    def test_approval_replay_no_second_merge(self):
        self.ready(); self.c.handle(update('/approve T001 '+HEAD,uid=2)); self.c.handle(update('/approve T001 '+HEAD,uid=3)); self.assertEqual(len(self.gh.merges),1)
    def test_protected_diff_blocked(self):
        t=self.launch(); self.gh.changes=[{'filename':'.github/workflows/ci.yml','status':'modified'}]; self.cu.finish_dev(t['run_id']); self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'BLOCKED'); self.assertEqual(len(self.cu.created),1)
    def test_finished_without_pr_is_not_done(self):
        t=self.launch(); self.cu.runs[t['run_id']]['status']='FINISHED'; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'BLOCKED')
    def test_unknown_cursor_status_is_not_done(self):
        t=self.launch(); self.cu.runs[t['run_id']]['status']='SOMETHING_NEW'; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'BLOCKED')
    def test_wait_for_ci(self):
        t=self.launch(); self.cu.finish_dev(t['run_id']); self.gh.ci_result='WAIT'; self.c.tick(); self.c.tick(); self.assertEqual(len(self.cu.created),1)
    def test_ci_failure_queues_bounded_repair(self):
        t=self.launch(); self.cu.finish_dev(t['run_id']); self.c.tick(); self.gh.ci_result='FAIL'; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'PENDING'); self.assertEqual(self.gh.closed_prs,[7])
    def test_watchdog_requests_not_assumes_cancel(self):
        t=self.launch(); self.clock.now+=5500; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'CANCELLING'); self.assertTrue(self.cu.cancelled)
        self.cu.runs[t['run_id']]['status']='CANCELLED'; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'BLOCKED')
    def test_pause_does_not_claim_cancellation(self):
        t=self.launch(); self.c.handle(update('/pause',uid=2)); self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'DEVELOPING'); self.assertEqual(self.cu.cancelled,[])
    def test_stop_cancel_and_confirm(self):
        t=self.launch(); self.c.handle(update('/stop',uid=2)); self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'CANCELLING'); self.cu.runs[t['run_id']]['status']='CANCELLED'; self.c.tick(); self.assertEqual(self.db.task('T001')['state'],'BLOCKED')
    def test_launch_payload_no_service_secrets(self):
        self.launch(); text=self.cu.created[0]['prompt']; self.assertNotIn('fake-gh',text); self.assertNotIn('fake-cursor',text); self.assertNotIn('1:fake',text)
    def test_backlog_change_requires_migration(self):
        b=backlog(); b[0]['description']='changed'
        with self.assertRaises(ValueError): Controller(self.cfg,self.db,self.gh,self.cu,self.tg,b)
    def test_repo_state_not_reusable_elsewhere(self):
        with self.assertRaises(ValueError): Controller(replace(self.cfg,repo='other/repo'),self.db,self.gh,self.cu,self.tg,backlog())
    def test_no_second_launch_while_waiting_approval(self):
        self.ready(); self.c.tick(); self.assertEqual(len(self.cu.created),2)
    def test_flush_reports_from_persisted_events(self):
        self.launch(); self.c.flush(); n=len(self.tg.sent); self.c.flush(); self.assertEqual(len(self.tg.sent),n); self.assertGreater(n,0)
    def test_ambiguous_create_reuses_id(self):
        original=self.cu.create
        ids=[]
        def fail_once(agent_id,*args,**kwargs):
            ids.append(agent_id)
            if len(ids)==1: raise ProviderError('Cursor')
            return original(agent_id,*args,**kwargs)
        self.cu.create=fail_once
        self.c.handle(update('/resume'))
        with self.assertRaises(ProviderError): self.c.tick()
        self.assertEqual(self.db.task('T001')['state'],'LAUNCHING_DEV')
        self.c.tick(); self.assertEqual(ids[0],ids[1]); self.assertEqual(self.db.launch_count(self.c.day()),1)
    def test_provider_error_redacts_secret(self):
        self.assertNotIn('token',str(ProviderError('Telegram',401)))
