-- what do we know about X
SELECT kind,key,body FROM search WHERE body LIKE '%X%' OR key LIKE '%X%';
-- where does a symbol live
SELECT repo,path,line,summary FROM code_map WHERE symbol LIKE '%X%';
-- before running an unfamiliar command
SELECT trigger,symptom,fix FROM gotcha WHERE scope IN ('global','<REPO>');
SELECT name,command,notes FROM recipe WHERE scope IN ('global','<REPO>');
-- is another agent already on this
SELECT session,scope,branch,task,status,updated_at FROM work_log WHERE status IN ('open','blocked');
-- has this fork already been settled
SELECT question,chosen,rejected,rationale FROM decision WHERE topic LIKE '%X%';
-- what may have rotted
SELECT * FROM stale;

thread is deliberately OUTSIDE the search view, so query it directly:
  SELECT source,state,title,verdict,last_seen FROM thread
   WHERE state IN ('new','acting') ORDER BY last_seen DESC LIMIT 20;
  -- what was consciously declined and why (the record nothing upstream keeps):
  SELECT title,verdict,last_seen FROM thread WHERE state='declined' ORDER BY last_seen DESC;

Writes hold the same file as other agents, so always write with a timeout:
  sqlite3 -cmd ".timeout 5000" @DB@ "<sql>"
