import json
from pathlib import Path
from .schemas import SchemaRegistry
REQUIRED_ROLES={"sizer","researcher","master","brainstormer","test_designer","planner","plan_reviewer","implementer","test_author","test_executor","code_reviewer","documenter","alignment_checker","failure_diagnostician","skill_curator","frontier_advisor"}
def validate_tree(root):
    root=Path(root); errors=[]
    try:
        tools=json.loads((root/"config/tools.json").read_text())
        models=json.loads((root/"config/models.json").read_text())
    except Exception as e:
        return [f"invalid configuration: {e}"]
    for role in REQUIRED_ROLES:
        for f in [root/f"agents/{role}/agent.json",root/f"agents/{role}/model.json",root/f"agents/{role}/prompt.md"]:
            if not f.exists(): errors.append(f"missing {f}")
        if (root/f"agents/{role}/agent.json").exists():
            try:
                c=json.loads((root/f"agents/{role}/agent.json").read_text()); s=root/f"schemas/{c['output_schema']}.schema.json"
                if not s.exists(): errors.append(f"missing schema {s}")
                if len(c.get("tools",[]))!=len(set(c.get("tools",[]))): errors.append(f"duplicate tools in {role}")
                if set(c.get("tools",[]))!=set(tools["role_allowlists"].get(role,[])):
                    errors.append(f"tool manifest drift for {role}")
                if c.get("model_tier") not in models.get("tiers",{}): errors.append(f"unknown model tier for {role}")
            except Exception as e: errors.append(f"invalid role {role}: {e}")
    return errors
