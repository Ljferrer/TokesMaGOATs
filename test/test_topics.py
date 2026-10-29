import json
import tempfile
import unittest
from pathlib import Path
from topics import contexts, project_name, activity


class TopicTests(unittest.TestCase):
    def test_worktrees(self):
        self.assertEqual(project_name('/home/user/.codex/worktrees/abc/Example'), 'Example')
        self.assertEqual(project_name('/home/user/GitHub/Example/.claude/worktrees/fix'), 'Example')

    def test_parent_inheritance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'sessions'
            root.mkdir()
            (root.parent / 'session_index.jsonl').write_text(json.dumps(dict(id='parent',thread_name='Build export feature'))+'\n')
            for session,parent,cwd in [('child','parent','/tmp/elsewhere'),('parent',None,'/home/user/GitHub/Example')]:
                payload=dict(id=session,cwd=cwd,source={'subagent':{'thread_spawn':{'parent_thread_id':parent}}})
                (root / (session+'.jsonl')).write_text(json.dumps(dict(type='session_meta',payload=payload))+'\n')
            result=contexts({'sources':[dict(provider='Codex',path=str(root))]})
            child=result['Codex','child']
            self.assertEqual(child['project'],'Example')
            self.assertEqual(child['title'],'Build export feature')
            self.assertEqual(child['activity'],'Implementation')
            self.assertEqual(child['basis'],'Inherited parent task')

    def test_unknown_and_reviews(self):
        self.assertEqual(activity(''), 'Unclassified work')
        self.assertEqual(activity('Review implementation plan'), 'Reviews & audits')
