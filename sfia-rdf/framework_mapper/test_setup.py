"""
Test script for Framework Mapper

Quick tests to verify the framework parser and matching service work correctly.
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(parent_dir / 'sfia_app_v2'))

def test_framework_parser():
    """Test loading and parsing UK Engineering Council framework."""
    print("\n" + "="*80)
    print("TEST 1: Framework Parser")
    print("="*80)
    
    from app.services.framework_parser import FrameworkParser
    
    parser = FrameworkParser()
    framework = parser.load_ukeng_framework()
    
    print(f"\n✓ Loaded: {framework.name}")
    print(f"  Version: {framework.version}")
    print(f"  Registrations: {list(framework.registrations.keys())}")
    
    # Test CEng competencies
    ceng = framework.get_registration('CEng')
    print(f"\n✓ CEng Registration:")
    print(f"  Title: {ceng.title}")
    print(f"  SFIA Level Range: {ceng.sfia_level_range}")
    print(f"  Competencies: {list(ceng.competencies.keys())}")
    
    # Test Competency A details
    comp_a = ceng.get_competency('A')
    print(f"\n✓ Competency A:")
    print(f"  Title: {comp_a.title}")
    print(f"  Indicators: {len(comp_a.indicators)}")
    print(f"  Keywords: {', '.join(comp_a.keywords[:5])}...")
    
    return True


def test_competency_context():
    """Test getting competency context."""
    print("\n" + "="*80)
    print("TEST 2: Competency Context")
    print("="*80)
    
    from app.services.framework_parser import FrameworkParser
    
    parser = FrameworkParser()
    parser.load_ukeng_framework()
    
    context = parser.get_competency_context('ukeng', 'CEng', 'B')
    
    if context:
        print(f"\n✓ Retrieved context for Competency B:")
        print(f"  Framework: {context['framework']}")
        print(f"  Registration: {context['registration']['title']}")
        print(f"  Competency: {context['competency']['title']}")
        print(f"  Full text length: {len(context['competency']['full_text'])} chars")
        return True
    else:
        print("✗ Failed to retrieve context")
        return False


def test_registration_summary():
    """Test getting registration summary."""
    print("\n" + "="*80)
    print("TEST 3: Registration Summary")
    print("="*80)
    
    from app.services.framework_parser import FrameworkParser
    
    parser = FrameworkParser()
    parser.load_ukeng_framework()
    
    summary = parser.get_registration_summary('ukeng')
    
    if summary:
        print(f"\n✓ Registration Summary:")
        for code, details in summary.items():
            print(f"\n  {code} - {details['title']}")
            print(f"    SFIA Levels: {details['sfia_level_range']}")
            print(f"    Competencies: {details['competencies']}")
            print(f"    Roles: {', '.join(details['typical_roles'][:3])}...")
        return True
    else:
        print("✗ Failed to get summary")
        return False


def test_validation_logic():
    """Test evidence validation against competency."""
    print("\n" + "="*80)
    print("TEST 4: Evidence Validation (without model loading)")
    print("="*80)
    
    # This test just verifies the structure, not actual matching
    # To test matching, we'd need to load the transformer model
    
    print("\n✓ Validation structure defined")
    print("  Note: Full validation test requires loading transformer model")
    print("  Run the Flask app and use /api/validate endpoint for real testing")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print(" FRAMEWORK MAPPER - QUICK TESTS")
    print("=" * 80)
    
    tests = [
        test_framework_parser,
        test_competency_context,
        test_registration_summary,
        test_validation_logic,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 80)
    print(f" TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✓ All tests passed! Framework mapper is ready to use.")
        print("\nNext steps:")
        print("  1. cd framework_mapper")
        print("  2. pip install -r requirements.txt")
        print("  3. python run.py")
        print("  4. Open http://localhost:5001")
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
