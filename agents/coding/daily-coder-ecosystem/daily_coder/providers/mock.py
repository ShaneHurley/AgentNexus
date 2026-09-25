from .base import Provider
from ..models import InvocationResult
class MockProvider(Provider):
    """Offline contract exercise. Never certifies repository correctness."""
    name="mock"
    def invoke(self,r):
        q=r.input_packet.get("request") or r.input_packet.get("ORIGINAL_REQUEST","")
        outputs={
          "sizer":{"profile":r.input_packet.get("profile","S"),"score":0,"reasons":["mock sizing"]},
          "researcher":{"question":"bounded repository reconnaissance","scope":"read-only mock","observations":[{"label":"UNKNOWN","claim":"No real repository evidence was collected by the mock provider.","locator":"mock:0"}],"unknowns":["implementation ground truth"]},
          "brainstormer":{"options":[{"name":"conventional","hypothesis":"Follow the smallest verified change path."}],"no_better_angle_found":True},
          "master":{"intent":q,"non_goals":["Unrequested refactors"],"invariants":["Preserve user intent"],"chosen_approach":"Mock dry-run only","rejected_alternatives":[],"scope":[],"risk":"unknown","acceptance_criteria":["Replace mock provider before modifying code"],"unresolved_questions":[]},
          "test_designer":{"criteria":[{"id":"AC-1","behavior":"Configured provider is required for real edits","proof":"provider conformance test"}],"test_required":False,"reason":"Mock run performs no code change."},
          "planner":{"change_units":[],"file_allowlist":[],"verification_commands":[],"rollback":"No changes to roll back.","unresolved_questions":[]},
          "plan_reviewer":{"verdict":"pass","findings":[],"checked":["No unresolved questions","No write scope"]},
          "implementer":{"changed_files":[],"commands":[],"observations":["Mock provider made no edits."]},
          "test_author":{"changed_test_files":[],"criterion_mapping":[],"negative_control":"not_applicable"},
          "test_executor":{"verdict":"pass","commands":[],"evidence":["Mock orchestration contract only"],"limitations":["No repository tests executed"]},
          "code_reviewer":{"verdict":"pass","findings":[],"reviewed_diff_first":True,"limitations":["No diff"]},
          "documenter":{"changed_docs":[],"summary":"No code change to document."},
          "alignment_checker":{"verdict":"pass","checks":{"intent_to_decision":True,"decision_to_plan":True,"plan_to_diff":True,"diff_to_tests":True,"diff_to_docs":True},"findings":[]},
          "skill_curator":{"verdict":"no_candidate","reason":"No verified reusable procedure emerged."},
          "failure_diagnostician":{"failure_class":"orchestration","first_failing_signal":"mock","evidence":[],"recommended_action":"stop","rationale":"Mock runs cannot diagnose real failures."},
          "frontier_advisor":{"decision":"No frontier decision is available in mock mode.","rationale":"Mock provider","confidence":"low","missing_evidence":["live provider"]},
        }
        out=outputs.get(r.role,{"status":"ok"})
        return InvocationResult(output=out,input_tokens=50,output_tokens=50,model="mock")
