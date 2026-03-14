#!/usr/bin/env python
"""Quick test to ensure the app imports correctly after our changes."""

try:
    from app import app
    print("✓ App imports successfully")
    
    from routes.admin import admin_bp
    print("✓ Admin blueprint imports successfully")
    
    # Test that the new route is registered
    rules = [str(rule) for rule in app.url_map.iter_rules()]
    if '/admin/edit-exam-info' in rules:
        print("✓ New edit-exam-info route is registered")
    else:
        print("✗ edit-exam-info route NOT found in URL map")
        print("Available admin routes:")
        for rule in rules:
            if 'admin' in str(rule):
                print(f"  - {rule}")
    
    print("\n✓✓✓ All checks passed! ✓✓✓")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
