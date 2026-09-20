import json
import unittest
from agentops.policy import validate_changes, parse_review, valid_pr, pr_number, authenticate_update
from tests.fakes import *


class PolicyTests(unittest.TestCase):
    def test_allow_scoped_new_file(self):
        self.assertTrue(validate_changes([{'filename':'trading_lab/data/a.py','status':'added'}],['trading_lab/data/'])[0])
    def test_workflow_is_protected(self):
        self.assertFalse(validate_changes([{'filename':'.github/workflows/ci.yml','status':'modified'}],['.github/'])[0])
    def test_controller_is_protected(self):
        self.assertFalse(validate_changes([{'filename':'agentops/controller.py','status':'modified'}],['agentops/'])[0])
    def test_existing_tests_protected(self):
        self.assertFalse(validate_changes([{'filename':'tests/test_policy.py','status':'modified'}],['tests/'])[0])
    def test_deletion_rejected(self):
        self.assertFalse(validate_changes([{'filename':'trading_lab/data/a.py','status':'removed'}],['trading_lab/data/'])[0])
    def test_rename_rejected(self):
        self.assertFalse(validate_changes([{'filename':'trading_lab/data/a.py','status':'renamed'}],['trading_lab/data/'])[0])
    def test_path_escape_rejected(self):
        self.assertFalse(validate_changes([{'filename':'trading_lab/data/../../agentops/a.py','status':'added'}],['trading_lab/data/'])[0])
    def test_scope_escape_rejected(self):
        self.assertFalse(validate_changes([{'filename':'trading_lab/other/a.py','status':'added'}],['trading_lab/data/'])[0])
    def test_empty_diff_rejected(self):
        self.assertFalse(validate_changes([],['trading_lab/'])[0])
    def test_secret_path_rejected(self):
        self.assertFalse(validate_changes([{'filename':'trading_lab/data/.env','status':'added'}],['trading_lab/data/'])[0])
    def test_valid_pr_number(self):
        self.assertEqual(pr_number('https://github.com/'+REPO+'/pull/7', REPO),7)
    def test_foreign_pr_rejected(self):
        with self.assertRaises(ValueError): pr_number('https://github.com/attacker/repo/pull/7', REPO)
    def test_draft_pr_rejected(self):
        p=FakeGitHub().pr(7); p['draft']=True
        self.assertFalse(valid_pr(p,REPO,'main'))
    def test_fork_pr_rejected(self):
        p=FakeGitHub().pr(7); p['head']['repo']['full_name']='attacker/repo'
        self.assertFalse(valid_pr(p,REPO,'main'))
    def test_review_exact_sha(self):
        obj={'verdict':'PASS','head_sha':HEAD,'blocking_findings':[],'test_commands':['python tests']}
        self.assertEqual(parse_review(json.dumps(obj),HEAD)['verdict'],'PASS')
        with self.assertRaises(ValueError): parse_review(json.dumps(obj),BASE)
    def test_review_cannot_pass_with_blockers(self):
        with self.assertRaises(ValueError): parse_review(json.dumps({'verdict':'PASS','head_sha':HEAD,'blocking_findings':['bug'],'test_commands':['tests']}),HEAD)
    def test_review_requires_actual_command_field(self):
        with self.assertRaises(ValueError): parse_review(json.dumps({'verdict':'PASS','head_sha':HEAD,'blocking_findings':[],'test_commands':[]}),HEAD)
    def test_plain_pass_is_not_evidence(self):
        with self.assertRaises(ValueError): parse_review('Everything looks good. PASS',HEAD)
    def test_owner_auth(self):
        self.assertIsNotNone(authenticate_update(update('/resume'),42,{42},NOW))
    def test_wrong_user(self):
        self.assertIsNone(authenticate_update(update('/resume',owner=43),42,{42},NOW))
    def test_wrong_chat(self):
        self.assertIsNone(authenticate_update(update('/resume',chat=43),42,{42},NOW))
    def test_old_and_future_messages(self):
        self.assertIsNone(authenticate_update(update('/resume',date=NOW-700),42,{42},NOW))
        self.assertIsNone(authenticate_update(update('/resume',date=NOW+100),42,{42},NOW))
    def test_channel_posts_not_authority(self):
        msg=update('/resume'); msg['message']['chat']['type']='channel'
        self.assertIsNone(authenticate_update(msg,42,{42},NOW))
    def test_anonymous_admin_not_authority(self):
        msg=update('/resume'); msg['message']['sender_chat']={'id':42}
        self.assertIsNone(authenticate_update(msg,42,{42},NOW))
    def test_bot_not_authority(self):
        msg=update('/resume'); msg['message']['from']['is_bot']=True
        self.assertIsNone(authenticate_update(msg,42,{42},NOW))
    def test_callback_identity(self):
        msg={'update_id':4,'callback_query':{'id':'c','from':{'id':42},'message':{'chat':{'id':42,'type':'private'},'date':NOW-2000},'data':'a:T001:'+HEAD}}
        self.assertEqual(authenticate_update(msg,42,{42},NOW)[0],'/approve T001 '+HEAD)
