from tools.ehr_tool import EHRAdapter

ehr = EHRAdapter()
print("Keys:", list(ehr._records.keys()))
p = ehr.get_patient_summary("Ramesh")
print("Result for Ramesh:", p.get('Name'))
