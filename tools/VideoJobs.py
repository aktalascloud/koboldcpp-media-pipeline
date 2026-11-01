"""Persistent request receipts, not an automatic retry queue. No prompts/keys stored."""
import hashlib,json,re,sqlite3,threading,time,uuid,os
from pathlib import Path
from contextlib import contextmanager

class JobConflict(ValueError):pass

class VideoJobs:
    def __init__(self,root):
        self.path=Path(root)/'logs/video-jobs.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.owner=uuid.uuid4().hex
        from BackendSupervisor import WindowsOperations
        operations=WindowsOperations();identity=operations.process(os.getpid())
        if not identity:raise RuntimeError('Cannot capture video receipt owner')
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, key_hash TEXT UNIQUE, fingerprint TEXT, status TEXT, stage TEXT, updated REAL, owner TEXT, receipt TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS owner (slot INTEGER PRIMARY KEY,pid INTEGER,ticks TEXT)')
            previous=db.execute('SELECT pid,ticks FROM owner WHERE slot=1').fetchone()
            if previous:
                live=operations.process(previous[0]) if previous[0]>0 else None
                same=live and str(live['created_ticks'])==previous[1]
                if same and previous[0]!=os.getpid():raise RuntimeError('Video receipt ledger belongs to an existing live frontend')
                restarted=not same
            else:restarted=True
            if restarted:db.execute("UPDATE jobs SET status='unknown',stage='server_restarted',updated=? WHERE status IN ('queued','running')",(time.time(),))
            db.execute('INSERT OR REPLACE INTO owner VALUES (1,?,?)',(os.getpid(),str(identity['created_ticks'])))
    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()
    def claim(self,payload,key=None,config_sha=''):
        if key is not None and (not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{8,128}',key)):raise ValueError('Idempotency-Key:8..128 ASCII letters/digits/_.:-')
        key_hash=hashlib.sha256(key.encode()).hexdigest() if key else None
        fingerprint=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        with self.lock,self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT id,fingerprint FROM jobs WHERE key_hash=?',(key_hash,)).fetchone() if key_hash else None
            if prior:
                if prior[1]!=fingerprint:raise JobConflict('Idempotency-Key already belongs to another payload/configuration')
                return self.get(prior[0]),False
            identity=uuid.uuid4().hex
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',(identity,key_hash,fingerprint,'queued','queue',time.time(),self.owner,json.dumps({'config_sha256':config_sha})))
        return self.get(identity),True
    def get(self,identity):
        if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{32}',identity):raise ValueError('Invalid request_id')
        with self._db() as db:row=db.execute('SELECT status,stage,updated,receipt FROM jobs WHERE id=?',(identity,)).fetchone()
        if row is None:raise KeyError(identity)
        return dict(request_id=identity,status=row[0],stage=row[1],updated=row[2],**json.loads(row[3]))
    def stage(self,identity,stage,**values):
        with self.lock,self._db() as db:
            row=db.execute('SELECT status,receipt FROM jobs WHERE id=?',(identity,)).fetchone()
            if row is None:raise KeyError(identity)
            if row[0] not in ('queued','running'):raise JobConflict('Job is no longer runnable')
            receipt={**json.loads(row[1]),**values}
            db.execute("UPDATE jobs SET status='running',stage=?,updated=?,receipt=? WHERE id=?",(stage,time.time(),json.dumps(receipt,ensure_ascii=False),identity))
    def finish(self,identity,result=None,error=None,status_code=None):
        value={'result':result} if result is not None else {'error':error,'http_status':status_code}
        with self.lock,self._db() as db:
            prior=db.execute('SELECT receipt,status,stage FROM jobs WHERE id=?',(identity,)).fetchone()
            if prior is None:raise KeyError(identity)
            if result is None and (prior[1]=='succeeded' or prior[2]=='cancelled_before_start'):return
            value={**json.loads(prior[0]),**value}
            db.execute('UPDATE jobs SET status=?,stage=CASE WHEN ? THEN \'completed\' ELSE stage END,updated=?,receipt=? WHERE id=?',('succeeded' if result is not None else 'failed',result is not None,time.time(),json.dumps(value,ensure_ascii=False),identity))
    def cancel_queued(self,identity):
        with self.lock,self._db() as db:
            row=db.execute('SELECT status FROM jobs WHERE id=?',(identity,)).fetchone()
            if row is None:raise KeyError(identity)
            if row[0]!='queued':raise JobConflict('Only a queued job can be cancelled; running Native is never aborted globally')
            db.execute("UPDATE jobs SET status='failed',stage='cancelled_before_start',updated=?,receipt=? WHERE id=?",(time.time(),json.dumps({'error':{'code':'job_cancelled'},'http_status':409}),identity))
        return self.get(identity)
