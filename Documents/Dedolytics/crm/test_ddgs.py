from ddgs import DDGS

query = 'site:linkedin.com/in/ "Stripe" "Head of Data"'
print(f"Querying DDGS: {query}")

try:
    results = DDGS().text(query, max_results=3)
    for res in results:
        print(f"TITLE: {res.get('title')}")
        print(f"BODY: {res.get('body')}")
        print("---")
except Exception as e:
    print(f"Error: {e}")
