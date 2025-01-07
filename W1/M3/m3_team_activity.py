import pandas as pd
from bs4 import BeautifulSoup
import requests
import json
res = requests.get('https://www.imf.org/external/datamapper/api/v1/NGDPD?periods=2025,2025')
# print(res.text)
jsonData = json.loads(res.text)
print(pd.DataFrame(jsonData['values']['NGDPD']))