# -*- coding: utf-8 -*-
import sys
sys.path.append(r'd:\project_pi4_llm')
from repair_estimator import load_catalog, filter_by_category

mats, labs = load_catalog(r'd:\project_pi4_llm\materials.csv', r'd:\project_pi4_llm\labor.csv')
print(f"Loaded {len(mats)} materials and {len(labs)} jobs.")

# Test filter for door issue
filtered_m = filter_by_category(mats, "Door", "ลูกบิดประตูห้องน้ำพัง ล็อคไม่ได้")
filtered_j = filter_by_category(labs, "Door", "ลูกบิดประตูห้องน้ำพัง ล็อคไม่ได้")

print("\n--- Test Filter for 'ลูกบิดประตูห้องน้ำพัง ล็อคไม่ได้' ---")
print("Filtered Materials:")
for k, v in filtered_m.items():
    print(f"  [{k}] {v['name']} ({v['price']} บ.)")

print("Filtered Jobs:")
for k, v in filtered_j.items():
    print(f"  [{k}] {v['name']} ({v['price']} บ., min {v['min']} บ.)")
