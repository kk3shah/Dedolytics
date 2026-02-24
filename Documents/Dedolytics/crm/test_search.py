from googlesearch import search

query = "Stripe Head of Data LinkedIn"
print(f"Querying Google: {query}")
results = search(query, num_results=3, advanced=True)
for res in results:
    print(f"TITLE: {res.title}")
    print(f"URL: {res.url}")
    print("---")
