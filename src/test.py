import yfinance as yf

ticker = yf.Ticker("NOW")
news = ticker.news
print(news[0]['content'])