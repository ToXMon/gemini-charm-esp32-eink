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

if __name__=='__main__': unittest.main()
