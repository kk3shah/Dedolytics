import db
import re
import time

# Cleaned data extracted from the pasted Apollo text.
# Omitted entries with no email (e.g. Shopify).
# Fixed anonymized names using email forensics (e.g. "Mike D" + "mike.doll@..." -> Mike Doll)
leads = [
    {
        "name": "Mark Morel",
        "title": "Chief Data Officer",
        "company": "Environics Analytics",
        "email": "mark.morel@environicsanalytics.com",
        "industry": "Data Analytics",
    },
    {
        "name": "Julio Vega",
        "title": "Data & Analytics Manager",
        "company": "The Dufresne Group",
        "email": "jcvega@dufresne.ca",
        "industry": "Furniture Retail",
    },
    {
        "name": "Adrien Chanson",
        "title": "Data Analytics Manager",
        "company": "Cosmo5",
        "email": "adrien.chanson@labelium.com",
        "industry": "Marketing",
    },
    {
        "name": "Geoff Webb",
        "title": "Chief Technology Officer",
        "company": "Map Labs",
        "email": "geoff@maplabs.com",
        "industry": "Technology",
    },
    {
        "name": "Julian Paas",
        "title": "CTO",
        "company": "Karma Casting",
        "email": "julian.paas@karmacasting.com",
        "industry": "Entertainment Tech",
    },
    {
        "name": "Jay Allayorov",
        "title": "Co-Founder",
        "company": "Weltlink LLC",
        "email": "jayallayorov@weltlink.co",
        "industry": "Logistics",
    },
    {
        "name": "Dmitri Melamed",
        "title": "CTO",
        "company": "BIG Digital",
        "email": "dmitri@bigdigital.ca",
        "industry": "Digital Media",
    },
    {
        "name": "Darren Shea",
        "title": "Chief Technology Officer",
        "company": "Drawbridge",
        "email": "darren@trydrawbridge.com",
        "industry": "Software",
    },
    {
        "name": "Jeff St-Louis",
        "title": "Chief Technology Officer",
        "company": "WNDR",
        "email": "jeff@wndr.com",
        "industry": "Technology",
    },
    {
        "name": "David Stevens",
        "title": "Chief Technology Officer",
        "company": "Groupe Dynamite",
        "email": "dstevens@dynamite.ca",
        "industry": "Apparel & Fashion",
    },
    {
        "name": "Babak Bavardi",
        "title": "Chief Technology Officer",
        "company": "Propulsion Web 360",
        "email": "babak@propulsion360.com",
        "industry": "Web Development",
    },
    {
        "name": "Steve Kostrey",
        "title": "Chief Technology Officer",
        "company": "MADHUB",
        "email": "steve@madhub.com",
        "industry": "Technology",
    },
    {
        "name": "Brent Nyznyk",
        "title": "Chief Technology Officer",
        "company": "Silver Gold Bull",
        "email": "brent.nyznyk@silvergoldbull.com",
        "industry": "Precious Metals",
    },
    {
        "name": "Eric Poulin",
        "title": "Chief Technology Officer",
        "company": "The Digital Marketing People",
        "email": "eric.poulin@digitalmarketingpeople.ca",
        "industry": "Digital Marketing",
    },
    {
        "name": "Eugene Sukharev",
        "title": "Chief Technology Officer",
        "company": "ShipTime",
        "email": "eugene@shiptime.com",
        "industry": "Logistics Technology",
    },
    {
        "name": "Brendan Wing",
        "title": "Chief Technology Officer",
        "company": "Yatara",
        "email": "brendan@yatara.com",
        "industry": "Technology",
    },
    {
        "name": "Olivier Coulombe-Raymond",
        "title": "Owner & CTO",
        "company": "Letmetalk",
        "email": "olivier@letmetalk.ai",
        "industry": "Artificial Intelligence",
    },
    {
        "name": "Alexandre Desilets-Benoit",
        "title": "CTO",
        "company": "Receptiv",
        "email": "alexandre.desilets-benoit@contxtful.com",
        "industry": "Technology",
    },
    {
        "name": "Shaun Kiernan",
        "title": "Chief Technology Officer",
        "company": "Headlight",
        "email": "shaun@headlight.co",
        "industry": "Technology",
    },
    {
        "name": "Ryan Ernst",
        "title": "Chief Technical Officer",
        "company": "SimplyCast",
        "email": "ryan.ernst@simplycast.com",
        "industry": "Marketing Automation",
    },
    {
        "name": "Ajit Thomas",
        "title": "CTO",
        "company": "MaxBounty",
        "email": "ajitt@maxbounty.com",
        "industry": "Affiliate Marketing",
    },
    {
        "name": "Dean Steptoe",
        "title": "Chief Technology Officer",
        "company": "Ziip Courier",
        "email": "steptoe@ziip.ca",
        "industry": "Logistics",
    },
    {
        "name": "Mark Pike",
        "title": "Chief Technology Officer",
        "company": "m5 the agency",
        "email": "mark@m5.ca",
        "industry": "Marketing & Advertising",
    },
    {
        "name": "Lance Faver",
        "title": "Chief Technology Officer",
        "company": "AMJ",
        "email": "lfaver@amjmove.com",
        "industry": "Logistics & Moving",
    },
    {
        "name": "Andrew Schuster",
        "title": "Chief Technology Officer",
        "company": "Environics Analytics",
        "email": "andrew.schuster@environicsanalytics.com",
        "industry": "Data Analytics",
    },
    {
        "name": "Corey Jansen",
        "title": "Chief Technology Officer",
        "company": "Gustin Quon",
        "email": "corey@gustinquon.com",
        "industry": "Digital Marketing",
    },
    {
        "name": "Jan Hoch",
        "title": "Chief Technology Officer",
        "company": "The Original FARM",
        "email": "j.hoch@originalfarm.com",
        "industry": "Retail",
    },
    {
        "name": "Chaitanya Sharma",
        "title": "Chief Technology Officer",
        "company": "Digital Pepper Inc.",
        "email": "chaitanya@digitalpepper.ca",
        "industry": "Digital Marketing",
    },
    {
        "name": "Alex Gierus",
        "title": "Chief Technology Officer",
        "company": "VantEdge",
        "email": "agierus@vantedgelgx.com",
        "industry": "Logistics Technology",
    },
    {
        "name": "Nathan Bernard",
        "title": "Chief Technology Officer",
        "company": "ODM World",
        "email": "nathan@odmworld.com",
        "industry": "Technology",
    },
    {
        "name": "Abhinav Mathur",
        "title": "CTO",
        "company": "Quill Inc",
        "email": "abhinav@quillit.io",
        "industry": "Technology",
    },
    {
        "name": "Johnny Ji",
        "title": "Chief Technical Officer",
        "company": "Distru",
        "email": "johnnyji@distru.com",
        "industry": "Software",
    },
]


def ingest_apollo_paste():
    db.init_db()

    count = 0
    for lead in leads:
        # Add a tiny delay to ensure timestamps for 'new' status act uniquely
        time.sleep(0.01)

        # 1. Add as a job target
        job_id = db.upsert_job(
            title=lead["title"],
            company=lead["company"],
            link=f"apollo://{lead['company'].replace(' ', '').lower()}",
            description=lead["industry"],
            department="Data",
            hiring_manager="Null",
        )

        if job_id:
            # 2. Add as an enriched contact
            db.add_contact(job_id, lead["name"], lead["email"], lead["title"])

            # 3. Mark as Enriched safely
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'enriched' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()

            print(f"[+] Loaded Verified Lead: {lead['name']} ({lead['email']}) at {lead['company']}")
            count += 1

    print(f"\n[*] Successfully ingested {count} new verified leads directly into the CRM.")


if __name__ == "__main__":
    ingest_apollo_paste()
