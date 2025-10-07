# Protection Plan Fixes - Quick Summary

## 🐛 Issues Fixed

### 1. Retention Policy Field Name ❌ → ✅
- **Wrong:** `maxCount` 
- **Correct:** `retentionCount`
- **Impact:** Protection plans failed to create with validation error

### 2. Enable/Disable Field Name ❌ → ✅
- **Wrong:** `enabled: true/false`
- **Correct:** `suspend: false/true` (inverted logic!)
- **Impact:** Enable/disable operations didn't work correctly

### 3. Immutable Spec Limitation 🚫
- **Problem:** NDK API doesn't allow editing protection plan specs after creation
- **Solution:** Removed edit functionality entirely
- **Workaround:** Delete and recreate plan with new settings

---

## 📝 Schema Changes

### Correct NDK Protection Plan Schema
```yaml
apiVersion: dataservices.nutanix.com/v1alpha1
kind: ProtectionPlan
metadata:
  name: my-plan
  namespace: default
spec:
  # IMMUTABLE FIELDS (cannot be changed after creation)
  schedule: "0 2 * * *"
  retentionPolicy:
    retentionCount: 5        # ✅ Use retentionCount (NOT maxCount)
    maxAge: "720h"           # ✅ maxAge is correct
  selector:
    matchLabels:
      app: myapp
  
  # MUTABLE FIELD (can be changed)
  suspend: false             # ✅ Use suspend (NOT enabled)
                             # false = enabled, true = disabled
```

---

## 🔧 Code Changes

### Backend (app.py)
```python
# ✅ Correct retention policy
retention_policy = {
    "retentionCount": retention_count  # NOT maxCount
}

# ✅ Correct enable/disable
# Enable = set suspend to False
plan_spec['suspend'] = False

# Disable = set suspend to True  
plan_spec['suspend'] = True

# ✅ Return suspend field (not enabled)
return jsonify({
    'suspend': plan_spec.get('suspend', False)
})
```

### Frontend (app.js)
```javascript
// ✅ Correct status check
const isActive = plan.suspend !== true;  // NOT plan.enabled !== false

// ✅ Display status
const statusBadge = isActive 
    ? '<span class="badge bg-success">Active</span>'
    : '<span class="badge bg-secondary">Disabled</span>';
```

---

## 🧪 Test Results

All 10 tests passing:
1. ✅ Login
2. ✅ List Protection Plans  
3. ✅ Create Protection Plan (with retentionCount + suspend)
4. ✅ Get Single Protection Plan
5. ✅ Disable Protection Plan (suspend=true)
6. ✅ Enable Protection Plan (suspend=false)
7. ✅ Trigger Protection Plan
8. ✅ Get Protection Plan History
9. ✅ Delete Protection Plan
10. ✅ Get Dashboard Stats

---

## 📋 Files Modified

| File | Changes |
|------|---------|
| `app.py` | Fixed field names, removed PUT endpoint |
| `static/app.js` | Fixed suspend logic, removed edit function |
| `templates/index.html` | Removed edit mode fields |
| `test_protection_plans.py` | Fixed tests, removed update test |
| `README.md` | Added warnings, removed edit docs |
| `CHANGELOG.md` | Detailed change documentation |

---

## ⚠️ Important Notes

### What Users CAN Do:
- ✅ Create protection plans
- ✅ Delete protection plans
- ✅ Enable/Disable (suspend/resume) plans
- ✅ Trigger manual snapshots
- ✅ View snapshot history

### What Users CANNOT Do:
- ❌ Edit schedule after creation
- ❌ Edit retention policy after creation
- ❌ Edit selector after creation

### Workaround:
To "edit" a plan: **Delete it and create a new one**

---

## 🚀 Quick Test

Run the test script to verify everything works:
```bash
python3 test_protection_plans.py
```

Expected output: All 10 tests should pass ✅

---

## 📚 API Reference

### Create Protection Plan
```bash
POST /api/protectionplans
{
  "name": "daily-backup",
  "namespace": "default",
  "schedule": "0 2 * * *",
  "retentionCount": 5,        # ✅ Use retentionCount
  "selector": {
    "matchLabels": {"app": "myapp"}
  }
}
```

### Enable/Disable
```bash
# Enable (sets suspend=false)
POST /api/protectionplans/{namespace}/{name}/enable

# Disable (sets suspend=true)
POST /api/protectionplans/{namespace}/{name}/disable
```

### Get Plan (returns suspend field)
```bash
GET /api/protectionplans/{namespace}/{name}

Response:
{
  "name": "daily-backup",
  "namespace": "default",
  "suspend": false,           # ✅ Returns suspend (not enabled)
  "schedule": "0 2 * * *",
  ...
}
```

---

## 🎯 Key Takeaways

1. **Field Names Matter:** NDK uses `retentionCount` and `suspend`, not `maxCount` and `enabled`
2. **Inverted Logic:** `suspend: false` = enabled, `suspend: true` = disabled
3. **Immutable Specs:** Schedule, retention, and selector cannot be edited after creation
4. **Only Suspend is Mutable:** Enable/disable is the only operation that modifies existing plans
5. **Delete & Recreate:** To change immutable fields, delete the plan and create a new one

---

## ✅ Verification Checklist

- [x] Retention policy uses `retentionCount` field
- [x] Enable/disable uses `suspend` field with inverted logic
- [x] Edit functionality removed from UI
- [x] PUT endpoint removed from backend
- [x] Tests updated and passing
- [x] Documentation updated with warnings
- [x] Frontend displays correct status based on `suspend` field
- [x] All API endpoints working correctly