import yfinance as yf

ticker = yf.Ticker("HUBS")
news = ticker.news
print(news[0]['content'])