from ddgs import DDGS

with DDGS() as ddgs:
    results = [r for r in ddgs.text("restaurants mississauga ontario", max_results=5)]
    print(results)
