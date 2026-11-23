import importlib.util
import pathlib
import unittest
import httpx

path=pathlib.Path(__file__).resolve().parents[1]/'experiments'/'decision-routing'/'evaluate.py'
spec=importlib.util.spec_from_file_location('decision_eval',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class DecisionEvaluationTests(unittest.TestCase):
    def test_choice_and_refusal(self):
        count=0
        def handler(request):
            nonlocal count
            count+=1
            if count==1: return httpx.Response(200,json={'answers':[{'type':'choice','choice':'image','confidence':.8}],'usage':{'input_tokens':123}})
            return httpx.Response(200,json={'answers':[{'type':'refusal'}]})
        cases=[{'id':'one','input':'draw','expected':'image'},{'id':'two','input':'unclear','expected':'clarify'}]
        with httpx.Client(transport=httpx.MockTransport(handler)) as client: rows=module.evaluate(client,'model',cases)
        self.assertEqual(rows[0]['choice'],'image')
        self.assertEqual(rows[0]['usage']['input_tokens'],123)
        self.assertEqual(rows[1]['status'],'refusal_or_invalid')
        self.assertIsNone(rows[1]['choice'])

    def test_venice_jev_contract(self):
        import json
        def handler(request):
            self.assertEqual(request.url.host,'api.venice.ai')
            body=json.loads(request.content)
            self.assertEqual(body['state'],'draw')
            self.assertIn('image',body['questions']['route']['criteria'])
            return httpx.Response(200,json={'answers':{'route':{'type':'choice','choice':'image','confidence':.9}}})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rows=module.evaluate(client,'clef-api',[{'id':'one','input':'draw','expected':'image'}],'venice','jev')
        self.assertEqual(rows[0]['choice'],'image')
        self.assertEqual(rows[0]['confidence'],.9)

    def test_selects_lowest_diem_cost_from_supported_online_models(self):
        def model(name, input_price, output_price, offline=False):
            return {'id':name,'type':'decision','model_spec':{'offline':offline,'pricing':{'input':{'diem':input_price},'output':{'diem':output_price}}}}
        catalog={'data':[model('jev-latest',.042,0),model('clef-api',.05,.05),model('untested',0,0)]}
        self.assertEqual(module.cheapest_venice_model(catalog),'jev-latest')
        catalog['data'][0]['model_spec']['offline']=True
        self.assertEqual(module.cheapest_venice_model(catalog),'clef-api')
        catalog['data'][1]['model_spec']['offline']=True
        with self.assertRaises(ValueError): module.cheapest_venice_model(catalog)

if __name__=='__main__': unittest.main()
