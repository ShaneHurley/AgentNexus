from .models import Phase

LINEAR=[Phase.NEW,Phase.INTAKE,Phase.SIZE,Phase.RESEARCH,Phase.BRAINSTORM,Phase.DECIDE,Phase.TEST_DESIGN,Phase.PLAN,Phase.PLAN_REVIEW,Phase.READY_TO_BUILD,Phase.IMPLEMENT,Phase.TEST_AUTHOR,Phase.TEST_EXECUTE,Phase.CODE_REVIEW,Phase.DOCUMENT,Phase.ALIGNMENT,Phase.ACCEPTANCE,Phase.COMPLETE]
TERMINAL={Phase.COMPLETE,Phase.FAILED,Phase.CANCELLED}
EXCEPTIONAL={Phase.WAITING_HUMAN,Phase.WAITING_JOB,Phase.ESCALATED,Phase.DIAGNOSE,Phase.FAILED,Phase.CANCELLED}
# Phases a run may re-enter after a wait, escalation, or diagnosis.
RESUMABLE=set(LINEAR[1:-1])

def allowed_transition(old:Phase,new:Phase)->bool:
    if old in TERMINAL: return False
    if new in EXCEPTIONAL: return True
    if old in EXCEPTIONAL: return new in RESUMABLE
    if old==Phase.SIZE and new in {Phase.RESEARCH,Phase.DECIDE}: return True
    if old==Phase.RESEARCH and new==Phase.DECIDE: return True
    if old==Phase.DECIDE and new in {Phase.TEST_DESIGN,Phase.PLAN}: return True
    if old==Phase.PLAN_REVIEW and new in {Phase.PLAN,Phase.DECIDE}: return True
    # S_TRIVIAL skips TEST_AUTHOR and DOCUMENT while keeping ALIGNMENT for acceptance.
    if old==Phase.IMPLEMENT and new==Phase.TEST_EXECUTE: return True
    if old==Phase.CODE_REVIEW and new==Phase.ALIGNMENT: return True
    if old==Phase.TEST_EXECUTE and new in {Phase.IMPLEMENT,Phase.ESCALATED}: return True
    if old==Phase.CODE_REVIEW and new in {Phase.IMPLEMENT,Phase.DECIDE}: return True
    if old==Phase.ALIGNMENT and new in {Phase.PLAN,Phase.DOCUMENT,Phase.DECIDE}: return True
    try: return LINEAR.index(new)==LINEAR.index(old)+1
    except ValueError: return False
