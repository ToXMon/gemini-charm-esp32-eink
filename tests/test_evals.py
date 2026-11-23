import copy
import unittest
from evals.analyze import analyze, compare, validate, word_error_rate
from evals.import_decision import convert
from evals.import_host_media import convert as import_media
from evals.deepeval_export import export
from evals.cost import token_estimate, unit_estimate
from decimal import Decimal


def fixture():
    return {'schema_version':1,'run_id':'r','variant':'v','dataset_id':'set1','scope':'device_end_to_end','cost_capture_complete':True,'cases':[
        {'case_id':'a','trial':1,'expected_route':'image','observed_route':'image','status':'completed','review':'accepted','latency_ms':100,'expected_stages':['decision','image'], 'expected_transcript':'blue duck','observed_transcript':'blue dog', 'stages':[
            {'stage':'decision','status':'ok','cost':{'currency':'diem_credit','kind':'actual','amount':'0.02'}},
            {'stage':'image','status':'ok','cost':{'currency':'usd','kind':'actual','amount':'0.10'}}]},
        {'case_id':'b','trial':1,'expected_route':'song','observed_route':'speech','status':'failed','review':'rejected','latency_ms':200,'stages':[
            {'stage':'speech','status':'failed','cost':{'currency':'usd','kind':'actual','amount':'0.03'}}]}]}

class EvalTests(unittest.TestCase):
    def test_report_counts_failed_spend_and_separates_credits(self):
        report=analyze(fixture())
        self.assertEqual(report['route_accuracy'],.5)
        self.assertEqual(report['costs']['usd']['actual_cost_per_accepted'],'0.13')
        self.assertEqual(report['costs']['diem_credit']['actual_cost_per_accepted'],'0.02')
        self.assertEqual(report['word_error_rate']['aggregate'],.5)
        self.assertEqual(report['trajectory'],{'measured':1,'passed':1})
        self.assertEqual(report['latency_ms']['p95_nearest_rank'],200)
    def test_unknown_cost_never_treated_as_free(self):
        run=fixture();run['cases'][1]['stages'][0]['cost'].update(kind='unknown',amount=None)
        self.assertIsNone(analyze(run)['costs']['usd']['actual_cost_per_accepted'])
        run=fixture();run['cost_capture_complete']=False
        self.assertIsNone(analyze(run)['costs']['usd']['actual_cost_per_accepted'])
    def test_pending_review_suppresses_unit_cost(self):
        run=fixture();run['cases'][1]['review']='pending'
        self.assertIsNone(analyze(run)['costs']['usd']['actual_cost_per_accepted'])

    def test_mixed_estimate_is_not_actual(self):
        run=fixture();run['cases'][1]['stages'][0]['cost']['kind']='estimate'
        self.assertIsNone(analyze(run)['costs']['usd']['actual_cost_per_accepted'])
    def test_duplicate_and_invalid_number_rejected(self):
        run=fixture();run['cases'].append(copy.deepcopy(run['cases'][0]))
        with self.assertRaises(ValueError): validate(run)
        run=fixture();run['cases'][0]['latency_ms']=float('nan')
        with self.assertRaises(ValueError): validate(run)
    def test_pairing_and_unmatched(self):
        a=fixture();b=copy.deepcopy(a);b['run_id']='b';b['cases'][1]['observed_route']='song';b['cases'].pop(0)
        result=compare(a,b);self.assertEqual((result['matched'],result['left_only'],result['route_right_only_correct']),(1,1,1))
    def test_transcript_empty_not_scored(self): self.assertIsNone(word_error_rate('','hello'))
    def test_import_decision_does_not_invent_cost(self):
        result=convert({'provider':'venice','model':'x','rows':[{'id':'a','expected':'image','choice':'image','status':'ok','latency_ms':123}]},'run','set1')
        self.assertEqual(result['scope'],'decision_only')
        self.assertEqual(analyze(result)['costs']['diem_credit']['unknown_stage_count'],1)

    def test_comparison_rejects_label_mismatch(self):
        a=fixture();b=copy.deepcopy(a);b['cases'][0]['expected_route']='song'
        with self.assertRaises(ValueError): compare(a,b)
    def test_missing_latency_and_stage_fields_rejected(self):
        run=fixture();del run['cases'][0]['latency_ms']
        with self.assertRaises(ValueError): validate(run)

    def test_compare_rejects_dataset_or_scope_mismatch(self):
        a=fixture();b=copy.deepcopy(a);b['dataset_id']='other'
        with self.assertRaises(ValueError): compare(a,b)
        b=copy.deepcopy(a);b['scope']='decision_only'
        with self.assertRaises(ValueError): compare(a,b)
    def test_deepeval_export_has_no_transcripts(self):
        row=export(fixture())[0]
        self.assertEqual((row['actual_output'],row['expected_output']),('image','image'))
        self.assertNotIn('blue duck',str(row))

    def test_host_media_does_not_invent_routing(self):
        run=fixture();run['scope']='host_media'
        for case in run['cases']:
            case['expected_route']=None;case['observed_route']=None
        report=analyze(run)
        self.assertIsNone(report['route_accuracy'])
        self.assertEqual(report['route_correct'],0)
        self.assertIsNone(compare(run,copy.deepcopy(run))['both_correct'])
        with self.assertRaises(ValueError): export(run)
        run['cases'][0]['observed_route']='image'
        with self.assertRaises(ValueError):validate(run)

    def test_host_media_import_preserves_unknown_cost_and_unfinished_job(self):
        state={'speech':{'status':'succeeded','latency_ms':100,'actual_usd':'0.02'},
               'song':{'status':'http_error','latency_ms':2},
               'song_default':{'status':'queued','latency_ms':5,'job_id':'synthetic'}}
        run=import_media(state,'host','synthetic')
        report=analyze(run)
        self.assertIsNone(report['route_accuracy'])
        self.assertEqual(report['costs']['usd']['known_actual'],'0.02')
        self.assertEqual(report['costs']['usd']['unknown_stage_count'],2)
        self.assertEqual(run['cases'][2]['status'],'unknown')
        self.assertIsNone(run['cases'][2]['latency_ms'])
        self.assertIsNone(report['costs']['usd']['actual_cost_per_accepted'])

    def test_cost_estimates_use_exact_units(self):
        self.assertEqual(token_estimate(1000,200,'1.20','4'),Decimal('0.0020'))
        self.assertEqual(unit_estimate('2.5','.04'),Decimal('.100'))
        with self.assertRaises(ValueError): token_estimate(-1,0,'1','2')
        with self.assertRaises(ValueError): unit_estimate('NaN','1')

if __name__=='__main__':unittest.main()
