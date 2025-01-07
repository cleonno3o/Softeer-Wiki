import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime as dt
import json
import sqlite3
from enum import Enum

class Mode(Enum):
    EXTRACT = 'EXTRACT'
    TRANSFORM = 'TRANSFORM'
    LOAD = 'LOAD'

def writeLog(state: Mode, isStart: bool):
    with open('./W1/M3/data/etl_project_log.txt', 'a') as log:
        time = dt.datetime.now().strftime('%Y-%b-%d-%H-%M-%S')
        if isStart:
            log.write(f'{time}, [{state.value}] Started\n')
        else:
            log.write(f'{time}, [{state.value}] Ended\n')

def getSoup(url):
    response = requests.get(url)
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
    
state = Mode.EXTRACT
# <<< 
# Extract 
# >>>
writeLog(state, True)
url = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_%28nominal%29"
soup = getSoup(url)

table = soup.select_one('table.wikitable.sortable')
head = table.select('tr.static-row-header')
body = table.find_all('tr')

# RAW data JSON 파일로 저장
with open('./W1/M3/data/Countries_by_GDP.json', 'w', encoding='utf-8') as jsonFile:
    json.dump(table.text, jsonFile, ensure_ascii=False, indent=4)
jsonFile.close()
writeLog(state, False)
state = Mode.TRANSFORM
# <<<
# TRANSFORM
# >>>

# 표의 컬럼 추출
writeLog(state, True)
category = ''
organization = []
for i, item in enumerate(head[0].find_all('th')):
    # category 추출
    if (i == 0):
        category = item.text.strip()
    # 기관 추출
    else:
        organization.append(item.find('a').text)
regionDf = pd.read_csv('./W1/M3/data/region.csv')
# Table Parsing
infoAll = []
for rank, row in enumerate(body):
    if rank < 3: continue
    # 한 행의 정보를 담을 리스트
    info = []
    # 불필요한 정보를 제거
    while (row.sup != None):
        row.sup.decompose()
    # 정보 저장
    for idx, item in enumerate(row):
        value = item.text.strip()
        # 빈 셀 스킵
        if (value == ''): continue
        # 해당 기관의 정보가 없으면 예상치와 년도를 모두 0으로 설정
        elif (value == '—'): 
            info.append('NaN')
            info.append('NaN')
        # 정상 정보면 저장
        else: info.append(item.text.strip())
    # 문자열로 저장된 정보를 숫자로 변환
    for i in range(1, len(info)):
        # GDP 정보면 float
        if i % 2 != 0: info[i] = float(info[i].replace(',',''))
        # 년도 정보면 int
        else: info[i] = float(info[i].replace(',',''))
    # region 정보를 국가 이름과 매칭
    region = regionDf[regionDf['name'] == info[0]]['region'].values[0]
    info.insert(1, region)
    infoAll.append(info)
# DataFrame 컬럼 리스트 생성
tempColumn = head[1].text.strip('\n').split('\n')
columnList = [category, 'region'] + tempColumn
# 모든 기관의 정보가 담긴 DataFrame
gdpDf = pd.DataFrame(infoAll, columns=columnList)
gdpDf['Year'] = gdpDf['Year'].astype('Int64')
gdpDf
# IMF의 정보만 분리
gdpImf = gdpDf.iloc[:,:4]
gdpImf.rename(columns={'Forecast':'GDP', 'Country/Territory': 'Country'}, inplace=True)
gdpImf['GDP_USD_billion'] = round((gdpImf['GDP'] / 1000), 2)
gdpImf.sort_values('GDP_USD_billion', ascending=False, inplace=True)
gdpImf.reset_index(drop=True, inplace=True)
gdpImf
# GDP가 100B 이상 국가
gdpImf[gdpImf['GDP_USD_billion'] > 100]
# 각 Region 별 상위 5개국 평균 GDP
gdpImfGrouped = gdpImf.set_index(['region'])
temp = gdpImfGrouped.sort_values(by=['region', 'GDP_USD_billion'], ascending=[True, False]).groupby('region').head(5)['GDP_USD_billion']
gdpRegion = temp.groupby(temp.index).mean()
gdpRegion
writeLog(state, False)
state = Mode.LOAD
# <<<
# LOAD
# >>>
writeLog(state, True)
con = sqlite3.connect('./W1/M3/data/World_Economies.db')
gdpImf.to_sql('gdp',con, if_exists='replace')
writeLog(state, False)

con.cursor().execute(
    '''
    SELECT *
    FROM gdp
    WHERE GDP_USD_billion > 100;
''').fetchall()

con.cursor().execute(
    '''
    WITH rankedByRegionGdp AS (
        SELECT
            Country,
            region,
            GDP_USD_billion,
            ROW_NUMBER() OVER (PARTITION BY region ORDER BY GDP DESC) AS rank
        FROM gdp
    )
    SELECT region, AVG(GDP_USD_billion)
    FROM rankedByRegionGdp
    WHERE rank <= 5
    GROUP BY region;
    '''
).fetchall()