import requests



TALLY_URL = "http://localhost:9000"



# List of items from your bill that are broken

items_to_fix = [

    "SABER035",

    "SI BRITE TIP",

    "CATH TEMPO",

    "DES Stent"

]



def fix_item(name):

    xml = f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC><REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">

        <STOCKITEM NAME="{name}" ACTION="Alter">

            <NAME>{name}</NAME>

            <MAINTAININBATCHES>Yes</MAINTAININBATCHES>

            <USEEXPIRYDATE>Yes</USEEXPIRYDATE>

            <HASBATCHES>Yes</HASBATCHES>

        </STOCKITEM>

    </TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""

    

    try:

        r = requests.post(TALLY_URL, data=xml)

        print(f"Fixing {name}: {r.text}")

    except Exception as e:

        print(f"Error {name}: {e}")



print("--- STARTING REPAIR ---")

for item in items_to_fix:

    fix_item(item)

print("--- DONE ---")