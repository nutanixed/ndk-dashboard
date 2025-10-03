#!/usr/bin/env python3
"""
Schema Verification Script
Verifies that the NDK Dashboard uses the correct field names for Protection Plans
"""

import re
import sys

def check_file(filepath, patterns, description):
    """Check if file contains correct patterns and no incorrect ones"""
    print(f"\n📋 Checking {description}: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    all_good = True
    
    for pattern_type, pattern, expected in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        
        if pattern_type == 'must_have':
            if matches:
                print(f"   ✅ Found '{expected}': {len(matches)} occurrence(s)")
            else:
                print(f"   ❌ Missing '{expected}'")
                all_good = False
        
        elif pattern_type == 'must_not_have':
            if matches:
                print(f"   ❌ Found incorrect '{expected}': {len(matches)} occurrence(s)")
                for match in matches[:3]:  # Show first 3
                    print(f"      - {match.strip()}")
                all_good = False
            else:
                print(f"   ✅ No incorrect '{expected}' found")
    
    return all_good

def main():
    print("🔍 NDK Dashboard Schema Verification")
    print("=" * 60)
    
    all_checks_passed = True
    
    # Check app.py (backend)
    backend_patterns = [
        ('must_have', r"'retentionCount':\s*retention", "retentionCount field"),
        ('must_have', r"'suspend':\s*", "suspend field"),
        ('must_have', r"\.get\('suspend',", "suspend field getter"),
        ('must_not_have', r"'maxCount':\s*(?!.*#.*old|.*comment)", "maxCount field (should be retentionCount)"),
        ('must_not_have', r"'enabled':\s*(?!.*#.*comment|.*class)", "enabled field in spec (should be suspend)"),
    ]
    
    if not check_file('app.py', backend_patterns, 'Backend (app.py)'):
        all_checks_passed = False
    
    # Check app.js (frontend)
    frontend_patterns = [
        ('must_have', r"plan\.suspend", "plan.suspend reference"),
        ('must_have', r"suspend\s*!==\s*true", "suspend !== true check"),
    ]
    
    if not check_file('static/app.js', frontend_patterns, 'Frontend (app.js)'):
        all_checks_passed = False
    
    # Check test script
    test_patterns = [
        ('must_have', r"\.get\('suspend'", "suspend field in tests"),
        ('must_not_have', r"plan\['enabled'\]", "enabled field (should be suspend)"),
    ]
    
    if not check_file('test_protection_plans.py', test_patterns, 'Test Script'):
        all_checks_passed = False
    
    # Check for removed edit functionality
    print(f"\n📋 Checking Edit Functionality Removal")
    
    with open('app.py', 'r') as f:
        app_content = f.read()
    
    # Check that PUT method is removed from the route
    if "methods=['GET', 'DELETE']" in app_content and "methods=['GET', 'PUT', 'DELETE']" not in app_content:
        print("   ✅ PUT method removed from protection plan route")
    else:
        print("   ❌ PUT method still present in protection plan route")
        all_checks_passed = False
    
    with open('static/app.js', 'r') as f:
        js_content = f.read()
    
    # Check that edit button is removed
    if 'Edit</button>' not in js_content or 'onclick="editPlan' not in js_content:
        print("   ✅ Edit button removed from UI")
    else:
        print("   ❌ Edit button still present in UI")
        all_checks_passed = False
    
    # Check that editPlan function is removed
    if 'function editPlan(' not in js_content and 'async function editPlan(' not in js_content:
        print("   ✅ editPlan() function removed")
    else:
        print("   ❌ editPlan() function still present")
        all_checks_passed = False
    
    # Final summary
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ All schema verifications PASSED!")
        print("\n✨ The dashboard correctly uses:")
        print("   - retentionCount (not maxCount)")
        print("   - suspend (not enabled)")
        print("   - Edit functionality removed (immutable spec)")
        return 0
    else:
        print("❌ Some schema verifications FAILED!")
        print("\n⚠️  Please review the errors above and fix them.")
        return 1

if __name__ == '__main__':
    sys.exit(main())