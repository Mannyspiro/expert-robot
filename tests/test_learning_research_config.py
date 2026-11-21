"""Host composition tests with canonical synthetic stores, not institutional SSO."""
import json
from pathlib import Path
import tempfile
import unittest

from merlin.identity import OIDCIdentityResolver
from merlin.learning_evidence_eval import _setup_demo, grade_evidence_response
from merlin.learning_research_config import (ENVIRONMENT_KEY, build_learning_research_api,
    learning_research_projects_from_environment)


class LearningResearchConfigurationTests(unittest.TestCase):
    def test_absent_or_blank_configuration_stays_disabled(self):
        for environment in ({},{ENVIRONMENT_KEY:''},{ENVIRONMENT_KEY:' \t\n'}):
            self.assertIsNone(learning_research_projects_from_environment(environment))

    def test_valid_host_map_is_copied_without_identity_or_project_creation(self):
        environment={ENVIRONMENT_KEY:'{"college-a":"existing-a","college-b":"existing-b"}'}
        result=learning_research_projects_from_environment(environment)
        self.assertEqual(result,{'college-a':'existing-a','college-b':'existing-b'})
        result['college-a']='changed-local-copy'
        self.assertEqual(learning_research_projects_from_environment(environment)['college-a'],'existing-a')

    def test_duplicate_alias_invalid_shape_and_control_characters_fail_closed(self):
        invalid=['{}','null','[]','true','{"college":"a","college":"b"}',
            '{"college-a":"same","college-b":"same"}','{"college":true}',
            '{"college":{"project":"nested"}}','{" college":"project"}',
            '{"college":" project"}','{"college\\n":"project"}','{"college":"project\\u0000"}']
        for raw in invalid:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                learning_research_projects_from_environment({ENVIRONMENT_KEY:raw})

    def test_configuration_is_bounded_and_errors_do_not_echo_contents(self):
        marker='synthetic-deployment-marker-must-not-echo'
        for raw in ('x'*65537,json.dumps({str(i):str(i) for i in range(129)}),'{'+marker):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError) as failure:
                learning_research_projects_from_environment({ENVIRONMENT_KEY:raw})
            self.assertNotIn(marker,str(failure.exception))

    def make_stores(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return _setup_demo(Path(temporary.name),'d'*40)

    def test_composition_shares_exact_stores_resolver_and_frozen_evidence(self):
        fixture,platform,registry,_,_,_,learner,scope,pins,frozen=self.make_stores()
        calls=[]
        def synthetic_host_resolver(headers):
            calls.append(True)
            return learner if headers.get('Authorization')=='Bearer synthetic-test-only' else None
        api=build_learning_research_api(platform=platform,registry=registry,
            identity_resolver=synthetic_host_resolver,tenant_projects={learner.tenant_id:'synthetic-learning-evidence'})
        self.assertIs(api.platform,platform);self.assertIs(api.registry,registry)
        self.assertIs(api.evidence_service.platform,platform)
        self.assertIs(api.identity_resolver,synthetic_host_resolver)
        self.assertIsNone(api.lab_bridge);self.assertEqual(calls,[])
        path='/api/learning/courses/'+scope['course_id']+'/research/'
        body={key:scope[key] for key in ('course_version','manifest_sha256')}
        for case in fixture['cases']:
            status,response=api.dispatch(path+'evidence',{'Authorization':'Bearer synthetic-test-only'},
                {**body,'query':case['query']})
            self.assertEqual(status,200)
            self.assertTrue(grade_evidence_response(case['case_id'],response,pinned_sources=pins,
                expected_binding={'tenant_id':learner.tenant_id,'project_id':'synthetic-learning-evidence',**scope},
                expected_source_manifest_ref=frozen['source_manifest_ref'])['passed'])
        status,response=api.dispatch(path+'lab',{'Authorization':'Bearer synthetic-test-only'},
            {**body,'lesson_id':'titan-structural-lab','run_id':'not-enabled','prediction':'No lab capability is configured.'})
        self.assertEqual(status,503);self.assertEqual(response['error'],'research_service_unavailable')

    def test_missing_project_is_not_provisioned_by_composition(self):
        _,platform,registry,_,_,_,learner,_,_,_=self.make_stores()
        with registry._connect() as db:before=db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        with self.assertRaises(ValueError):
            build_learning_research_api(platform=platform,registry=registry,identity_resolver=lambda headers:learner,
                tenant_projects={learner.tenant_id:'missing-project'})
        with registry._connect() as db:after=db.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        self.assertEqual(before,after)
        with self.assertRaises(KeyError):registry.inventory('missing-project')

    def test_missing_stores_resolver_or_oidc_verifier_are_not_fabricated(self):
        _,platform,registry,_,_,_,learner,_,_,_=self.make_stores()
        missing_oidc=OIDCIdentityResolver(issuer='https://synthetic.invalid',audience='synthetic-audience',token_verifier=None)
        valid={'platform':platform,'registry':registry,'identity_resolver':lambda headers:learner,
               'tenant_projects':{learner.tenant_id:'synthetic-learning-evidence'}}
        for changes in ({'platform':None},{'registry':None},{'identity_resolver':None},
                        {'identity_resolver':'not-an-authenticator'},{'identity_resolver':missing_oidc},
                        {'tenant_projects':None}):
            with self.subTest(field=next(iter(changes))),self.assertRaises(ValueError):
                build_learning_research_api(**{**valid,**changes})
        self.assertFalse(missing_oidc.configured)
        self.assertIsNone(missing_oidc({'Authorization':'Bearer synthetic-token'}))


if __name__=='__main__':unittest.main()
