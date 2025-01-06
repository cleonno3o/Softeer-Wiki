import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime as dt

url = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_%28nominal%29"
def getSoup(url):
    response = requests.get(url)
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
soup = getSoup(url)
table = soup.select('table.wikitable.sortable tbody > tr')
for row in table:
    print("======")
    print(row)
    for ele in row.select('td'):
        print(ele)
        print('---')