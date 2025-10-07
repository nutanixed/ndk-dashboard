# Changelog - NDK Dashboard Protection Plan Fixes

## 2024 - Schema Fixes and Immutable Spec Handling

### Critical Bug Fixes

#### 1. Fixed Retention Policy Schema Mismatch
**Problem:** The dashboard was using `maxCount` for count-based retention, but the NDK API validation webhook requires `retentionCount`.

**Error Message:**
```
spec.retentionPolicy.retentionCount: Invalid value: 'null': Retention count must be set to a value between 1 and 15
```

**Solution:**
- Changed all references from `maxCount` to `retentionCount` in `app.py`
- Updated both create (POST) and update logic
- Kept `maxAge` for duration-based retention (this was already correct)

**Files Modified:**
- `app.py` (lines ~623, ~717)

---

#### 2. Fixed Enable/Disable Field Schema Mismatch
**Problem:** The dashboard was using an `enabled` boolean field, but NDK actually uses a `suspend` boolean field with inverted logic.

**NDK Schema:**
- `suspend: false` = Plan is enabled/active
- `suspend: true` = Plan is disabled/suspended

**Solution:**
- Backend (`app.py`):
  - Changed all references from `enabled` to `suspend`
  - Enable endpoint now sets `suspend: False`
  - Disable endpoint now sets `suspend: True`
  - List and get endpoints return `suspend` field instead of `enabled`

- Frontend (`app.js`):
  - Updated `renderProtectionPlans()` to check `plan.suspend !== true`
  - Updated `editPlan()` to handle suspend field correctly

**Files Modified:**
- `app.py` (lines ~547, ~587, ~791, ~834)
- `static/app.js` (line ~375)

---

#### 3. Removed Edit Functionality (Immutable Spec Limitation)
**Problem:** NDK protection plan specs are immutable after creation. Attempting to update schedule, retention, or selector fields returns:

**Error Message:**
```
Spec is immutable for protectionPlan.dataservices.nutanix.com
```

**Solution:**
Since the NDK API doesn't allow editing protection plan specs, we removed the edit functionality entirely:

**Backend Changes (`app.py`):**
- Removed PUT method from `/api/protectionplans/<namespace>/<name>` route
- Removed entire PUT implementation (~67 lines of code)
- Changed route decorator from `methods=['GET', 'PUT', 'DELETE']` to `methods=['GET', 'DELETE']`

**Frontend Changes (`static/app.js`):**
- Removed "Edit" button from action buttons in plan list
- Removed `editPlan()` function (~71 lines)
- Simplified `savePlan()` to only handle creation (removed isEditMode logic)
- Removed edit mode references from `showCreatePlanModal()`

**HTML Changes (`templates/index.html`):**
- Removed three hidden input fields used for edit mode tracking:
  - `plan-edit-mode`
  - `plan-original-name`
  - `plan-original-namespace`

**Test Changes (`test_protection_plans.py`):**
- Removed Test 5 (Update Protection Plan) entirely
- Renumbered subsequent tests (6→5, 7→6, 8→7, 9→8, 10→9, 11→10)
- Added cleanup logic to delete existing plan before creating new one

**Documentation Changes (`README.md`):**
- Added warning note about immutable specs
- Removed "Edit existing protection plans" from feature list
- Updated enable/disable descriptions to clarify they are suspend/resume operations
- Removed PUT endpoint from API table
- Removed "Update a Protection Plan" example

**Files Modified:**
- `app.py` (removed ~67 lines, changed route decorator)
- `static/app.js` (removed ~71 lines, simplified modal logic)
- `templates/index.html` (removed 3 hidden fields)
- `test_protection_plans.py` (removed 1 test, renumbered others)
- `README.md` (added warnings, removed edit documentation)

---

### What Still Works

Despite the immutable limitation, users can still:
- ✅ Create protection plans with schedule, retention, and selector
- ✅ Delete protection plans
- ✅ Enable/Disable (suspend/resume) plans - this is the ONLY mutable field
- ✅ Manually trigger plans to create snapshots
- ✅ View snapshot history
- ✅ View plan details

### Workaround for "Editing"

If users need to change a protection plan's schedule, retention, or selector:
1. Delete the existing protection plan
2. Create a new protection plan with the desired settings

**Note:** This will not affect existing snapshots created by the old plan.

---

### Technical Details

#### NDK API Schema Requirements
```yaml
spec:
  retentionPolicy:
    retentionCount: 5          # Integer 1-15 (for count-based retention)
    maxAge: "720h"             # Duration string (for time-based retention)
  suspend: false               # Boolean (false=enabled, true=disabled)
  schedule: "0 2 * * *"        # Cron expression (IMMUTABLE)
  selector:                    # Label selector (IMMUTABLE)
    matchLabels:
      app: myapp
```

#### Mutable vs Immutable Fields
- **Mutable:** `suspend` (can be changed via enable/disable endpoints)
- **Immutable:** `schedule`, `retentionPolicy`, `selector` (cannot be changed after creation)

---

### Test Results

All tests pass successfully after fixes:
- ✅ Test 1: Login
- ✅ Test 2: List Protection Plans
- ✅ Test 3: Create Protection Plan (with correct retentionCount and suspend fields)
- ✅ Test 4: Get Single Protection Plan
- ✅ Test 5: Disable Protection Plan (suspend=true)
- ✅ Test 6: Enable Protection Plan (suspend=false)
- ✅ Test 7: Trigger Protection Plan (creates snapshots)
- ✅ Test 8: Get Protection Plan History
- ✅ Test 9: Delete Protection Plan
- ✅ Test 10: Get Dashboard Stats

---

### Migration Notes

If you have existing code that uses the old schema:

**Old (Incorrect):**
```python
{
  "retentionPolicy": {
    "maxCount": 5  # ❌ Wrong field name
  },
  "enabled": true  # ❌ Wrong field name
}
```

**New (Correct):**
```python
{
  "retentionPolicy": {
    "retentionCount": 5  # ✅ Correct field name
  },
  "suspend": false  # ✅ Correct field name (inverted logic)
}
```

**Frontend Display:**
```javascript
// Old (Incorrect)
const isActive = plan.enabled !== false;

// New (Correct)
const isActive = plan.suspend !== true;
```

---

### Files Changed Summary

1. **app.py** - Backend API fixes
   - Fixed retention policy field name (maxCount → retentionCount)
   - Fixed enable/disable field (enabled → suspend)
   - Removed PUT endpoint implementation

2. **static/app.js** - Frontend JavaScript fixes
   - Updated suspend field handling
   - Removed edit functionality

3. **templates/index.html** - Modal HTML cleanup
   - Removed edit mode hidden fields

4. **test_protection_plans.py** - Test script updates
   - Fixed field references
   - Removed update test
   - Renumbered tests

5. **README.md** - Documentation updates
   - Added immutability warnings
   - Removed edit documentation
   - Updated API examples

---

### Lessons Learned

1. **Always validate against actual API schema** - Don't assume field names based on common conventions
2. **Check API validation webhooks** - They provide detailed error messages about schema mismatches
3. **Test with real API** - Mock tests might not catch schema validation issues
4. **Document limitations clearly** - Immutable specs are an API limitation, not a bug
5. **Inverted boolean logic** - Some APIs use "suspend" instead of "enabled" with opposite meaning

---

### Future Considerations

1. **Snapshot Management:** Consider adding ability to delete individual snapshots
2. **Bulk Operations:** Add ability to enable/disable multiple plans at once
3. **Plan Templates:** Create reusable templates for common protection scenarios
4. **Validation:** Add client-side validation to prevent invalid retention values
5. **Better Error Messages:** Show user-friendly messages when API validation fails