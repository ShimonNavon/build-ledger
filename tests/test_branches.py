import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('branches',pathlib.Path(__file__).resolve().parents[1]/'tools/sync_branches.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class BranchLifecycle(unittest.TestCase):
    def test_rename_delete_and_detached_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);repo=root/'example';repo.mkdir()
            def git(*args):return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True)
            git('init','-b','main');git('-c','user.name=Test','-c','user.email=test@example.com','commit','--allow-empty','-m','<script>untrusted title</script>')
            git('switch','-c','old-name');git('branch','-m','making-zoom')
            first=mod.scan(root)
            self.assertEqual({b['name'] for b in first['branches']},{'main','making-zoom'})
            self.assertEqual([b['name'] for b in first['branches'] if b['current']],['making-zoom'])
            self.assertEqual(first['branches'][0]['subject'],'<script>untrusted title</script>')
            git('switch','main');git('branch','-D','making-zoom');git('checkout','--detach')
            second=mod.scan(root)
            self.assertEqual([b['name'] for b in second['branches']],['main'])
            self.assertFalse(second['branches'][0]['current'])
            self.assertEqual(second['errors'],[])
if __name__=='__main__':unittest.main()
