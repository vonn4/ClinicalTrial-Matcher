"""Per-study evidence overview: counts and next questions, never an eligibility score."""
from .schemas import FollowupPlan, MatchOverview, TrialAssessment


def build_overview(assessment: TrialAssessment, plan: FollowupPlan | None) -> MatchOverview:
    by_id = {a.criterion_id: a for a in assessment.assessments}
    counts = {'met': 0, 'not_met': 0, 'unknown': 0, 'clinical_review': 0}
    triggered, failed_inclusions = [], []
    for c in assessment.criteria:
        a = by_id.get(c.id)
        if a is None:
            counts['unknown'] += 1
            continue
        counts[a.status] += 1
        if c.kind == 'exclusion' and a.exclusion_triggered:
            triggered.append(c.source_text)
        if c.kind == 'inclusion' and a.status == 'not_met':
            failed_inclusions.append(c.source_text)
    questions = []
    if plan:
        linked = [q for q in plan.questions if any(l.nct_id == assessment.nct_id for l in q.linked_criteria)]
        questions = [q.question for q in sorted(linked, key=lambda q: -q.priority)[:3]]
    return MatchOverview(
        total=len(assessment.criteria), met=counts['met'], not_met=counts['not_met'],
        unknown=counts['unknown'], clinical_review=counts['clinical_review'],
        exclusions_triggered=triggered[:5], inclusions_failed=failed_inclusions[:5],
        resolved_by_rules=sum(1 for a in assessment.assessments if a.source == 'rules'),
        resolved_by_model=sum(1 for a in assessment.assessments if a.source == 'model' and a.status in {'met', 'not_met'}),
        top_missing_questions=questions)


def with_overviews(assessments: list[TrialAssessment], plan: FollowupPlan | None) -> list[TrialAssessment]:
    return [a.model_copy(update={'overview': build_overview(a, plan)}) for a in assessments]
