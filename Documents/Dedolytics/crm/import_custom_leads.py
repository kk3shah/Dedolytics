import db
import time

RAW_CSV_DATA = """company_name,email,category
Agape Christian Counselling,georgeh@interlog.com,Counselling
Asian Outreach International Canada,info@asianoutreach.ca,Nonprofit
Canada in Prayer,prayer@canadainprayer.com,Nonprofit
JFJ Hope Centre,helpline@jfjhopecentre.ca,Nonprofit
Suraj Bal Gupta CPA CGA,suraj@surajgupta.ca,Accounting/Tax
Lucy Peng CPA,lucypengcpa@gmail.com,Accounting/Tax
Ajay Lekhi CPA CGA,lekhiajay@hotmail.com,Accounting/Tax
Don-Nel's Accounting Tax Services,don-nelsaccounting@bellnet.ca,Accounting/Tax
H&R Block (Mississauga),hrblock.53978@hrblock.ca,Accounting/Tax
AccountXperts,info@accountxperts.ca,Accounting/Tax
Enterprise Accounting and Tax Services,info@enterpriseaccountingandtax.ca,Accounting/Tax
Zaheda Dulai CGA,info@dulaicga.com,Accounting/Tax
Rockwood Dental (Dr. Glenn McKay),info@rockwooddental.com,Dentist
Wang Physio & Rehab Centre,wang.physio@yahoo.com,Physiotherapy
LV Rehabilitation Clinic,lvrehabilitation@gmail.com,Rehab/Physio
Dixie Square Health Clinic,dixiesquarehealth@gmail.com,Clinic
Lake Oasis Wellness Centre,lakeoasis388@gmail.com,Wellness
IRSVAK Health Services,rana.siddiki@gmail.com,Health Services
Evergreen Wellness Centre,hankxiao@hotmail.com,Wellness
Massage Hong Kong Professional,badretdinov@yahoo.com,Massage
Wild Lotus Spa,evayang2016@hotmail.com,Spa
Rahi's Beauty Salon,raheelarehman3@gmail.com,Beauty Salon
DiCilia Hair & Beauty Salon,info@diciliasalon.com,Beauty Salon
Bruce Salon and Spa,brucesalonandspa@gmail.com,Beauty Salon
Nails R Us Supply Ltd,sales@nailsrus.ca,Salon Supplies
ATS Auto Collision & Repair Centre,atsauto@live.com,Auto Body/Repair
ProZone Auto Collision and Repair,info@prozoneauto.com,Auto Repair
Arak Auto Inc,arak_auto@hotmail.com,Auto Repair
Keeyez Auto Group,librando.gianluca@yahoo.ca,Auto Repair/Dealer
BoSo MODE AUTO INC.,raf@bosomode.ca,Auto Repair
The Auto Spa Ltd.,info@autospa.com,Auto Detailing
Action Auto Glass,info@actionautoglass.ca,Auto Glass
Apple Auto Glass,apple2311@belroncanada.com,Auto Glass
Streetsville Hyundai,sales@streetsvillehyundai.ca,Car Dealership
George T Florea Barrister & Solicitor,gflorea@florealaw.ca,Law Firm
Law Offices of Uzma Ufaq,uzmalaw01@gmail.com,Law Firm
Jugpall & Sodhi Law Firm,sharan@jugpallsodhilaw.ca,Law Firm
MAK Law Professional Corp,khosalawyer@gmail.com,Law Firm
The Law Office of Mark Hogan,info@markhoganlaw.com,Law Firm
J P Mann Law Firm,jmann@jpmannlaw.com,Law Firm
Imran Akram - Barristers & Solicitors,imran@akram.pro,Law Firm
Hannan Hannan Barristers,contact@hannanhannan.com,Law Firm
Colin Hodgson Paralegal,hodgsoncolin1@gmail.com,Paralegal
All-Risks Insurance,jlombardo@all-risks.com,Insurance
Manulife Securities (John Di Salvo),john.disalvo@manulifesecurities.ca,Financial Services
EZ1 Plumbing Services Inc.,ez1plumbing@hotmail.com,Plumbing
Precise Plumbing & Drains Limited,info@mypreciseplumbing.com,Plumbing
Caribbean Authentic Restaurant,caribauthenticrest@bellnet.ca,Restaurant
Texas Longhorn,info@thetexaslonghorn.ca,Restaurant
Moxie's Grill & Bar (Mississauga),info@moxies.ca,Restaurant
Host Fine Indian Cuisine (Mississauga),info@welcometohost.com,Restaurant
Polka Bistro Caffe,polkabistrocaffe@hotmail.com,Restaurant
Wok This Way,takeout@bellnet.ca,Restaurant
Druxy's Famous Deli,comments@druxys.com,Restaurant/Deli
Guru Lukshmi,gurulukshmi@gmail.com,Restaurant
European Cleaning Company,imoveismaranata@yahoo.ca,Cleaning
Diamond Cleaning Service,diamond.cleaning.service@hotmail.com,Cleaning
The Cleaning Authority (Etobicoke–Mississauga East),tcaetobmiss@gmail.com,Cleaning
A & M Cleaning Services,gosia.kawa@gmail.com,Cleaning
Pro Plus Cleaning,propluscleaning@rogers.com,Cleaning
H2 Enhance Janitorial Services,h2enhanceservices@hotmail.com,Janitorial
Superior Air Duct Cleaning,info@superioradc.com,Duct Cleaning
SIMMCO-VAC,service@simmcovac.com,Duct Cleaning
Dewith Frazer Boxing and Fitness Inc,coach@dewithboxingstudio.com,Fitness
Chera Immigration Consultants,canasia_legal@hotmail.com,Immigration Services
4 Office Automation,elizabeth.singer@4office.com,Printing/Office Services
Jimbere Coaching and Consulting,jennifer@jimberecoachingandconsulting.com,Consulting/Coaching
Mariana Iskander (Century21),mariana.iskander@century21.ca,Real Estate
Parmeet Anand (Century 21),parmeet.anand@gmail.com,Real Estate
Marijan Koturic (Sutton Group),mkoturic@sutton.com,Real Estate
Remax Real Estate - Raja Matharu,raja@askraja.ca,Real Estate
Sandra Lopes (Royal LePage),sandralopes@royallepage.ca,Real Estate
Randolph Jones (Royal LePage),randolph@royallepage.ca,Real Estate
Waleed Khaled Elsayed (Keller Williams),waleedisaway@gmail.com,Real Estate"""


def import_raw_leads():
    print(f"\n--- Starting Custom Lead Importer at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    db.init_db()
    lines = RAW_CSV_DATA.strip().split("\n")[1:]  # Skip header
    success_count = 0

    for row in lines:
        if not row.strip():
            continue

        parts = row.split(",")
        if len(parts) >= 3:
            company_name = parts[0].strip()
            email = parts[1].strip()
            category = parts[2].strip()

            # Filter out the broken truncated emails the user accidentally pasted
            if email.endswith("..."):
                continue

            if email and "@" in email:
                lead_id = db.add_smb_lead(company_name, category, email, website="")
                if lead_id:
                    print(f"  [+] Imported: {company_name} ({email}) - {category}")
                    success_count += 1
                else:
                    print(f"  [-] Skipped: {email} (Already in DB)")

    print(f"\n--- Import Complete! Imported {success_count} fresh SMB leads. ---")


if __name__ == "__main__":
    import_raw_leads()
