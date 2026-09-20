"""Offline integration demo. Fake providers, no credentials, no actual market data."""
import json
from .config import Settings
from .controller import Controller
from .store import Store
from tests.fakes import BASE, HEAD, REPO, FakeGitHub, FakeCursor, FakeTelegram, Clock, backlog, update


def main():
    cfg=Settings(REPO,'fake','fake','1:fake',42,frozenset({42}),state_path=':memory:',allow_runs=True,spend_limit_confirmed=True,protection_confirmed=True)
    db=Store(':memory:'); gh=FakeGitHub(); cursor=FakeCursor(); tg=FakeTelegram(); clock=Clock()
    c=Controller(cfg,db,gh,cursor,tg,backlog(),clock=clock)
    events=[]
    def record(): events.append({'task':'T001','state':db.task('T001')['state']})
    record()
    c.handle(update('/resume')); c.tick(); record()
    cursor.finish_dev(db.task('T001')['run_id']); c.tick(); record()
    c.tick(); record()
    cursor.finish_qa(db.task('T001')['run_id']); c.tick(); record()
    assert not gh.merges, 'A merge must not happen before owner approval'
    c.handle(update('/approve T001 '+HEAD,uid=2)); c.tick(); record()
    c.flush()
    print(json.dumps({'mode':'OFFLINE_FAKE_PROVIDER_DEMO','external_calls':0,'paid_agents_started':0,'real_trades':0,'trace':events,'merge_requests_in_fake_github':len(gh.merges),'notifications_in_fake_telegram':len(tg.sent),'phase_2_remains':db.task('T002')['state']},indent=2))


if __name__ == '__main__': main()
