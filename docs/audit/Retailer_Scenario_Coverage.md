# Retailer Scenario Coverage

## Retailer 1: Delimited + Header + Multiple Record Types + Mixed Units/Weight + Blank Values + UOM Column

| Requirement | Coverage | Status | Gap |
|-------------|----------|--------|-----|
| Delimited | ✅ Full | Auto-detect delimiter |
| Header | ✅ Full | Header detection, configurable |
| Multiple Record Types | ✅ Full | Record type detection and flattening |
| Mixed Units + Weight | ✅ Full | Quantity resolution with priority |
| Blank values | ⚠️ Partial | Numeric parsing handles NULL patterns but blank detection in strings is basic |
| UOM Column | ⚠️ Partial | weight_uom_col supported in config but UOM not in canonical output |

**Status: ⚠️ Mostly covered — gaps in blank value handling and UOM propagation**

---

## Retailer 2: Fixed Width + No Header + Single Record Type + No Layout Initially Available

| Requirement | Coverage | Status | Gap |
|-------------|----------|--------|-----|
| Fixed Width | ⚠️ Partial | Detection identifies but cannot discover layout |
| No Header | ✅ Full | Handled |
| Single Record Type | ✅ Full | Handled |
| No Layout Initially Available | ❌ Missing | Layout Builder requires manual definition |

**Status: ❌ Not supported — needs record length detection and candidate layout generation**

---

## Retailer 3: Disclaimer + Header + Fixed Width + Multiline + Record Types + Store Header + Detail Records + Hierarchical Structure

| Requirement | Coverage | Status | Gap |
|-------------|----------|--------|-----|
| Disclaimer | ❌ Missing | No disclaimer detection |
| Header | ✅ Full | HDR prefix detection works |
| Fixed Width | ⚠️ Partial | Needs layout |
| Multiline | ✅ Full | HDR multiline flattening works |
| Record Types | ✅ Full | Record type detection works |
| Store Header | ⚠️ Partial | HDR header is detected but Store-specific headers not distinguished |
| Detail Records | ✅ Full | Detail layout works |
| Hierarchical Structure | ⚠️ Partial | Flattening flattens hierarchy (correct per architecture) |

**Status: ⚠️ Partially covered — disclaimer handling missing, store header not distinguished**

---

## Retailer 4: Standard Delimited + Simple Header + Units Only

| Requirement | Coverage | Status |
|-------------|----------|--------|
| Standard Delimited | ✅ Full | Fully supported |
| Simple Header | ✅ Full | Fully supported |
| Units Only | ✅ Full | Fully supported |

**Status: ✅ Fully covered**

---

## Additional Scenario: Sales File + Product Master File Joined by Business Keys

| Requirement | Coverage | Status | Gap |
|-------------|----------|--------|-----|
| Sales File | ✅ Full | Standard parsing works |
| Product Master File | ✅ Full | Standard parsing works |
| Join by Business Keys | ❌ Missing | No relationship detection or join support |
| Canonical Enrichment | ❌ Missing | No product attribute enrichment |

**Status: ❌ Not supported — needs relationship detection and canonical enrichment**

---

## Overall Coverage Summary

| Scenario | Status | Priority |
|----------|--------|----------|
| Retailer 1 (Delimited + Mixed) | ⚠️ 85% | High |
| Retailer 2 (Fixed-Width, No Layout) | ❌ 30% | **Critical** |
| Retailer 3 (HDR Multiline Fixed-Width) | ⚠️ 60% | **Critical** |
| Retailer 4 (Standard Delimited) | ✅ 100% | Complete |
| Sales + Product Master Join | ❌ 0% | High |
