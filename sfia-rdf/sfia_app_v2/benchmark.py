"""
Regression Benchmark for SFIA Skill Matcher
============================================
Run this to test matching accuracy across 10 ground truth cases.
Usage: python benchmark.py
"""
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)

# Ground truth test cases — evidence + the SFIA code that MUST appear in top 5
TEST_CASES = [
    {
        "label": "1. Software Development – Level 3",
        "expected_code": "PROG",
        "level_context": "Level 3",
        "evidence": """A new feature was required for a customer portal to allow users to update profile information online.

I was assigned responsibility for developing the backend API endpoint and associated database changes.

I implemented the endpoint following established coding standards, wrote unit tests, and participated in peer reviews. I sought guidance from senior developers when architectural questions arose and ensured my work aligned with the team's sprint objectives.

The feature was delivered on time, passed QA testing, and reduced manual update requests by 25%.

I worked as a developer within an agile team, reporting to an Engineering Manager. I was responsible for delivering assigned components to agreed quality standards but did not make architectural decisions or influence broader technical direction."""
    },
    {
        "label": "2. Software Development – Level 4",
        "expected_code": "SLEN",
        "level_context": "Level 4",
        "evidence": """The application performance was degrading as user demand increased.

I was responsible for leading the redesign of a performance-critical service component.

I analysed bottlenecks, redesigned inefficient queries, and refactored the service to improve scalability. I mentored junior developers and ensured changes aligned with architectural guidelines.

System response times improved by 35%, and production incidents related to performance were significantly reduced.

I operated as a Senior Developer within the product team, reporting to the Engineering Manager. I led technical solutions within the team and influenced design decisions locally but worked within enterprise standards set by architecture leadership."""
    },
    {
        "label": "3. Data Analysis – Level 4",
        "expected_code": "DAAN",
        "level_context": "Level 4",
        "evidence": """Marketing lacked consistent reporting on campaign effectiveness.

I was asked to produce reliable performance analysis for quarterly budget planning.

I consolidated multiple data sources, standardised metrics, and built automated dashboards. I worked directly with marketing managers to clarify reporting requirements.

Budget allocation decisions improved, increasing campaign ROI by 18%.

I worked within the BI team, reporting to the BI Manager. I independently led analytical workstreams and influenced stakeholders but did not define enterprise data strategy."""
    },
    {
        "label": "4. IT Governance – Level 5",
        "expected_code": "GOVN",
        "level_context": "Level 5",
        "evidence": """Project approvals lacked consistent risk oversight across IT initiatives.

I was responsible for establishing a structured governance process.

I defined approval criteria, introduced control checkpoints, and implemented reporting mechanisms for senior leadership. I advised project sponsors on risk mitigation requirements.

Project risk visibility improved, and compliance breaches reduced by 40%.

I reported to the CIO and acted as governance lead across the IT function. I defined governance standards within my remit and presented risk positions at executive forums. I was accountable for ensuring governance effectiveness across multiple delivery teams."""
    },
    {
        "label": "5. Information Security – Level 5",
        "expected_code": "SCTY",
        "level_context": "Level 5",
        "evidence": """Cloud adoption introduced inconsistent security controls across product teams.

I was accountable for embedding secure architecture standards across portfolios.

I established mandatory security design reviews, defined baseline controls, and advised programme leaders on risk trade-offs. I had authority to reject non-compliant designs.

Security findings reduced significantly, and regulatory audit outcomes improved.

I sat within the Cyber Security function, reporting to the Head of Security. I acted as security authority across several product teams and was accountable for solution-level security assurance, influencing risk decisions beyond my immediate team."""
    },
    {
        "label": "6. Service Operations – Level 5",
        "expected_code": "ITOP",
        "level_context": "Level 5",
        "evidence": """Critical systems experienced repeated outages affecting customer experience.

I was responsible for improving service resilience and operational governance.

I defined availability targets, led root cause reviews, and implemented proactive monitoring standards. I advised leadership on infrastructure investment trade-offs.

Service uptime improved to 99.9%, and incident recurrence reduced.

As IT Operations Manager reporting to the Head of IT, I was accountable for operational service outcomes across multiple teams. I balanced cost, performance, and risk when approving operational changes."""
    },
    {
        "label": "7. Risk Management – Level 4",
        "expected_code": "BURM",
        "level_context": "Level 4",
        "evidence": """Technology projects were progressing without consistent risk documentation.

I was asked to conduct structured risk assessments.

I identified risk scenarios, documented impact analysis, and supported project managers in defining mitigation actions.

Project risk transparency improved, and mitigation plans were formally tracked.

I worked within the Risk team, reporting to the Risk Manager. I independently conducted assessments but did not define risk policy or organisational appetite."""
    },
    {
        "label": "8. Enterprise Architecture – Level 6",
        "expected_code": "STPL",
        "level_context": "Level 6",
        "evidence": """Technology investment decisions were fragmented across business units.

I was accountable for defining a coherent enterprise architecture strategy.

I developed a target operating model, influenced executive investment decisions, and established architecture governance across all programmes. I resolved cross-functional conflicts regarding technology standards.

Technology duplication reduced, strategic alignment improved, and long-term cost efficiency increased.

Reporting to the CTO, I held enterprise-wide authority for architectural direction. I influenced executive strategy, defined standards adopted organisation-wide, and was accountable for long-term technology capability alignment."""
    },
    {
        "label": "9. Organisational Change – Level 6",
        "expected_code": "CIPM",
        "level_context": "Level 6",
        "evidence": """A digital transformation programme required significant cultural and process change.

I was accountable for establishing a change management framework across the organisation.

I defined the enterprise change model, coached senior leaders, and integrated change readiness metrics into governance reporting.

Programme adoption rates improved, and resistance to change reduced measurably.

Reporting to the COO, I shaped organisation-wide change strategy, influenced executive leadership behaviour, and was accountable for readiness across multiple transformation initiatives."""
    },
    {
        "label": "10. Learning & Development – Level 3",
        "expected_code": "ETMG",
        "level_context": "Level 3",
        "evidence": """New technical hires required onboarding training.

I was assigned to deliver structured induction sessions.

I prepared training materials and delivered workshops under guidance from the Capability Lead.

New hires achieved productivity milestones faster.

I operated as a trainer within the HR function, delivering predefined materials. I was responsible for session quality but did not design organisational capability strategy."""
    },
]

TOP_N = 5  # Expected code must appear in top N results to pass

def run_benchmark():
    print("Loading app context...")
    from app import create_app
    app = create_app()

    with app.app_context():
        from app.routes import get_services
        matcher = get_services()

        print(f"\n{'='*60}")
        print(f"  SFIA MATCHER BENCHMARK  ({len(TEST_CASES)} test cases, top-{TOP_N})")
        print(f"{'='*60}\n")

        passed = 0
        failed = 0
        results = []

        for case in TEST_CASES:
            result = matcher.match(case["evidence"], case["level_context"])
            matches = result.get("matches", [])
            codes_in_order = [m["code"] for m in matches]
            
            rank = None
            for i, code in enumerate(codes_in_order[:TOP_N]):
                if code == case["expected_code"]:
                    rank = i + 1
                    break

            ok = rank is not None
            if ok:
                passed += 1
                status = f"PASS  (rank {rank}/{TOP_N})"
            else:
                failed += 1
                top3 = " | ".join([f"{m['code']} ({m['label'][:20]})" for m in matches[:3]])
                status = f"FAIL  top3: [ {top3} ]"

            results.append((case["label"], case["expected_code"], status, ok))

        for label, expected, status, ok in results:
            icon = "OK " if ok else "!!  "
            print(f"  {icon} {label}")
            print(f"       Expected: {expected}  ->  {status}")
            print()

        print(f"{'='*60}")
        score = f"{passed}/{len(TEST_CASES)}"
        print(f"  SCORE: {score} passing")
        if failed > 0:
            print(f"  {failed} case(s) need attention.")
        else:
            print("  All cases passing!")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    run_benchmark()
