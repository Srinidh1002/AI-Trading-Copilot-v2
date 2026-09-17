from services.news import get_stock_news

news = get_stock_news("AAPL")

print(f"Articles: {len(news)}")

for article in news[:5]:
    print("-"*60)
    print(article["title"])
    print(article["publisher"])