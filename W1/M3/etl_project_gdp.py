import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime as dt
import sqlite3
import json
from tabulate import tabulate
from enum import Enum

class Mode(Enum):
    EXTRACT = 'EXTRACT'
    TRANSFORM = 'TRANSFORM'
    LOAD = 'LOAD'

def write_log(state: Mode, is_start: bool):
    with open('./W1/M3/data/etl_project_log.txt', 'a') as log:
        time = dt.datetime.now().strftime('%Y-%b-%d-%H-%M-%S')
        if is_start:
            log.write(f'{time}, [{state.value}] Started\n')
        else:
            log.write(f'{time}, [{state.value}] Ended\n')
    log.close()

def get_soup(url:str):
    response = requests.get(url)
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
    
# Table Parsing
def get_list_from_table():
    region_df = pd.read_csv('./W1/M3/data/region.csv')
    table_info_list = []
    for rank, row in enumerate(body):
        if rank < 3: continue
        # 한 행의 정보를 담을 리스트
        row_info = []
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
                row_info.append('NaN')
                row_info.append('NaN')
            # 정상 정보면 저장
            else: row_info.append(item.text.strip())
        # 문자열로 저장된 정보를 숫자로 변환
        for i in range(1, len(row_info)):
            # GDP 정보면 float
            if i % 2 != 0: row_info[i] = float(row_info[i].replace(',',''))
            # 년도 정보면 int
            else: row_info[i] = float(row_info[i].replace(',',''))
        # region 정보를 국가 이름과 매칭
        region = region_df[region_df['name'] == row_info[0]]['region'].values[0]
        row_info.insert(1, region)
        table_info_list.append(row_info)
    return table_info_list

# DataFrame 컬럼 리스트 생성
def get_column_list():
    category = ''
    organization = []
    for i, item in enumerate(head[0].find_all('th')):
        # category 추출
        if (i == 0):
            category = item.text.strip()
        # 기관 추출
        else:
            organization.append(item.find('a').text)
    tempColumn = head[1].text.strip('\n').split('\n')
    columnList = [category, 'region'] + tempColumn
    return columnList

def print_query_result(query:str):
    con = sqlite3.connect('./W1/M3/data/World_Economies.db')
    cursor = con.cursor()
    data = cursor.execute(query).fetchall()
    formatted_data = [
    [f"{x:,.2f}" if isinstance(x, float) else x for x in row]
    for row in data
    ]
    columns = [description[0] for description in cursor.description]
    print(tabulate(formatted_data, headers=columns, tablefmt='grid'))
    con.close()

state = Mode.EXTRACT

# <<< 
# Extract 
# >>>
write_log(state, True)
url = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_%28nominal%29"
soup = get_soup(url)

table = soup.select_one('table.wikitable.sortable')
head = table.select('tr.static-row-header')
body = table.find_all('tr')

# RAW data JSON 파일로 저장
with open('./W1/M3/data/Countries_by_GDP.json', 'w', encoding='utf-8') as json_file:
    json.dump(table.text, json_file, ensure_ascii=False, indent=4)
json_file.close()

write_log(state, False)
state = Mode.TRANSFORM

# <<<
# TRANSFORM
# >>>

write_log(state, True)
column_list = get_column_list()
table_info = get_list_from_table()

# 모든 기관의 정보가 담긴 DataFrame
gdp_df = pd.DataFrame(table_info, columns=column_list)
gdp_df['Year'] = gdp_df['Year'].astype('Int64')

# IMF의 정보만 분리
gdp_imf = gdp_df.iloc[:,:4]
gdp_imf.rename(columns={'Forecast':'GDP', 'Country/Territory': 'Country'}, inplace=True)
gdp_imf['GDP_USD_billion'] = round((gdp_imf['GDP'] / 1000), 2)
gdp_imf.sort_values('GDP_USD_billion', ascending=False, inplace=True)
gdp_imf.reset_index(drop=True, inplace=True)

# [SQL 사용하지 않고 접근하기]
# GDP가 100B 이상 국가
gdp_imf[gdp_imf['GDP_USD_billion'] > 100]
# 각 Region 별 상위 5개국 평균 GDP
gdp_imf_grouped = gdp_imf.set_index(['region'])
temp = gdp_imf_grouped.sort_values(by=['region', 'GDP_USD_billion'], ascending=[True, False]).groupby('region').head(5)['GDP_USD_billion']
gdp_region = temp.groupby(temp.index).mean()

write_log(state, False)
state = Mode.LOAD

# <<<
# LOAD
# >>>

write_log(state, True)
con = sqlite3.connect('./W1/M3/data/World_Economies.db')
gdp_imf.to_sql('gdp',con, if_exists='replace')
con.close()
write_log(state, False)

# [Query를 사용해 출력하기]
print_query_result(
    '''
    SELECT *
    FROM gdp
    WHERE GDP_USD_billion > 100;
    '''
    )

print_query_result(
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
)