from copy import deepcopy
import json

BASE = 'b' * 40
HEAD = 'a' * 40
REPO = 'owner/trading-lab'
NOW = 1800000000


class Clock:
    def __init__(self): self.now = NOW
    def __call__(self): return self.now


class FakeGitHub:
    def __init__(self):
        self.private = True
        self.protected = True
        self.base = BASE
        self.merges = []
        self.closed_issues = []
        self.closed_prs = []
        self.requests = []
        self.ci_result = 'PASS'
        self.changes = [{'filename': 'trading_lab/data/bars.py', 'status': 'added'}]
        self.pull = {
            'number': 7, 'state': 'open', 'draft': False, 'merged': False,
            'head': {'sha': HEAD, 'repo': {'full_name': REPO}},
            'base': {'ref': 'main', 'repo': {'full_name': REPO}},
        }
    def repository(self): return {'private': self.private}
    def branch(self, branch): return {'protected': self.protected, 'commit': {'sha': self.base}}
    def ensure_issue(self, task): return 1
    def pr(self, number): return deepcopy(self.pull)
    def files(self, number): return deepcopy(self.changes)
    def ci(self, sha): return self.ci_result, 'https://github.com/' + REPO + '/actions/runs/10'
    def merge(self, number, sha):
        self.merges.append((number, sha))
        self.pull.update(merged=True, state='closed', merge_commit_sha='c'*40)
        return {'merged': True, 'sha': 'c'*40}
    def close_issue(self, number): self.closed_issues.append(number)
    def close_pr(self, number):
        self.closed_prs.append(number)
        self.pull['state'] = 'closed'
    def request(self, title, body):
        self.requests.append((title, body))
        return 'https://github.com/' + REPO + '/issues/20'


class FakeCursor:
    def __init__(self):
        self.created = []
        self.runs = {}
        self.cancelled = []
    def create(self, agent_id, name, repo_url, ref, prompt, *, review=False, model=''):
        self.created.append({'id':agent_id, 'review':review, 'ref':ref, 'prompt':prompt})
        run_id = 'run-' + agent_id
        self.runs.setdefault(run_id, {'id':run_id, 'status':'RUNNING'})
        return run_id
    def run(self, agent_id, run_id): return deepcopy(self.runs[run_id])
    def cancel(self, agent_id, run_id): self.cancelled.append((agent_id, run_id))
    def finish_dev(self, run_id):
        self.runs[run_id].update(status='FINISHED', git={'branches':[{'repoUrl':'github.com/'+REPO,'prUrl':'https://github.com/'+REPO+'/pull/7'}]})
    def finish_qa(self, run_id, verdict='PASS'):
        self.runs[run_id].update(status='FINISHED', result=json.dumps({'verdict':verdict,'head_sha':HEAD,'blocking_findings':[] if verdict=='PASS' else ['Incorrect entry timestamp'],'test_commands':['python -m unittest discover -s tests -v'],'summary':'Mock review: integration test only'}))


class FakeTelegram:
    def __init__(self): self.sent=[]; self.answers=[]
    def send(self, chat_id, text, buttons=None): self.sent.append((chat_id,text,buttons)); return {'message_id':len(self.sent)}
    def answer(self, cid): self.answers.append(cid)


def backlog():
    return [{'id':'T001','title':'Causal bars','description':'Implement causal bars.','acceptance':['No future data'], 'allowed_prefixes':['trading_lab/data/','tests/added/'],'depends_on':[],'phase':1},
            {'id':'T002','title':'Later stage','description':'Gated later phase','acceptance':['Review'], 'allowed_prefixes':['docs/research/'],'depends_on':['T001'],'phase':2}]


def update(text, uid=1, owner=42, chat=42, date=NOW):
    return {'update_id':uid,'message':{'date':date,'chat':{'id':chat,'type':'private'},'from':{'id':owner,'is_bot':False},'text':text}}
