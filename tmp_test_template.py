from utils.template_renderer import render_exam_markdown

sample_patient={'kid_name':'A','kid_birthday':'2020','name':'P','phone':'0','address':'X'}
sample_exam={'exam_date':'2025-01-01','weight':'10','height':'90','history':'h','expected_date':'2025-02-01','total_money':100000,'drugs':[{'name':'D','quantity':'1','note':'n'}],'services':[{'name':'S','price':50000,'quantity':1,'prepaid_status':'PAID'}]}
custom={'header':'h','drugs_section':'d\n{drug_rows}','drug_row_template':'|{index}|{name}|','services_section':'s\n{service_rows}','service_row_template':'|{index}|{name}|','footer':'f'}
print(render_exam_markdown(sample_patient,sample_exam,custom_template=custom))
