"""Offline checks for provider input validation, checkpointing and safe reuse."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jsonschema.exceptions import ValidationError
import runway_operation as tool

class RunwayOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'studio').mkdir()
        (self.root/'studio/runway_catalog.json').write_text((tool.ROOT/'studio/runway_catalog.json').read_text())
        self.override=patch.object(tool,'ROOT',self.root);self.override.start();self.addCleanup(self.override.stop)
    def request(self,operation='get_organization',**fields):
        return {'operation':operation,'request_id':'a'*32,'path_params':{},'query':{},'body':{},**fields}
    def generation(self):
        return self.request('post_text_to_video',body={'model':'gen4.5','promptText':'A bicycle in a lab','ratio':'720:1280','duration':5},allow_mutation=True,allow_media_spend=True,estimated_credits=60)
    def test_catalog_unique_and_all_operations(self):
        ops=tool.catalog()['operations'];self.assertEqual(len(ops),65)
        self.assertEqual(len({x['id'] for x in ops}),65)
    def test_validates_model_specific_required_fields(self):
        r=self.generation();r['body'].pop('promptText')
        with self.assertRaises(ValidationError): tool.validate(r)
    def test_cannot_override_provider_path(self):
        with self.assertRaises(ValueError):tool.validate(self.request(query={'url':'https://elsewhere.test'}))
    def test_path_id_uses_provider_schema(self):
        with self.assertRaises(ValidationError):tool.validate(self.request('get_tasks_id',path_params={'id':'../organization'}))
    def test_mutation_requires_authorization(self):
        with self.assertRaises(ValueError):tool.validate(self.request('delete_avatars_id'))
    def test_balance_blocks_paid_submission(self):
        calls=[]
        def call(*args):calls.append(args);return {'creditBalance':1}
        with self.assertRaises(ValueError):tool.execute(self.generation(),call=call,checkpoint=lambda:None)
        self.assertEqual(len(calls),1)
    def test_checkpoint_precedes_submission_and_success_is_reused(self):
        events=[]
        def checkpoint():events.append('checkpoint')
        def call(method,path,*args):
            events.append(method+' '+path)
            if path=='/v1/organization':return {'creditBalance':5001}
            if method=='POST':return {'id':'task'}
            return {'status':'SUCCEEDED','output':['https://output.test/video.mp4']}
        result=tool.execute(self.generation(),call=call,checkpoint=checkpoint,archive=lambda *args:[{'url':'https://saved.test/clip.mp4'}])
        self.assertLess(events.index('checkpoint'),events.index('POST /v1/text_to_video'))
        self.assertEqual(result['state'],'completed')
        count=len(events);tool.execute(self.generation(),call=call,checkpoint=checkpoint);self.assertEqual(len(events),count)
    def test_unknown_submission_does_not_repeat(self):
        def call(method,path,*args):
            if method=='GET':return {'creditBalance':5001}
            raise TimeoutError('Response lost')
        with self.assertRaises(TimeoutError):tool.execute(self.generation(),call=call,checkpoint=lambda:None)
        with self.assertRaises(ValueError):tool.execute(self.generation(),call=lambda *args:self.fail('Must not resubmit'),checkpoint=lambda:None)
    def test_failure_saves_provider_code_and_message(self):
        def call(method,path,*args):
            if path=='/v1/organization':return {'creditBalance':5001}
            if method=='POST':return {'id':'task'}
            return {'status':'FAILED','failure':'Face not detected','failureCode':'FACE_NOT_FOUND'}
        with self.assertRaises(RuntimeError):tool.execute(self.generation(),call=call,checkpoint=lambda:None)
        result=json.loads((self.root/'studio/runway_jobs'/('a'*32)/'result.json').read_text())
        self.assertEqual(result['provider_detail']['failureCode'],'FACE_NOT_FOUND')
    def test_request_id_cannot_change_prompt(self):
        r=self.request();tool.execute(r,call=lambda *args:{'creditBalance':5001},checkpoint=lambda:None)
        with self.assertRaises(ValueError):tool.execute({**r,'operation':'get_avatars'},call=lambda *args:{},checkpoint=lambda:None)
    def test_workflow_uses_invocation_polling(self):
        r=self.request('post_workflows_id',path_params={'id':'82cf49fb-72c0-4701-a47c-05b632b69c47'},allow_mutation=True,allow_media_spend=True,estimated_credits=10)
        calls=[]
        def call(method,path,*args):
            calls.append(path)
            if path=='/v1/organization':return {'creditBalance':5001}
            if method=='POST':return {'id':'invocation'}
            return {'status':'SUCCEEDED','output':{'node':['https://output.test/video.mp4']}}
        tool.execute(r,call=call,checkpoint=lambda:None,archive=lambda *args:[])
        self.assertIn('/v1/workflow_invocations/invocation',calls)

if __name__=='__main__':unittest.main()
