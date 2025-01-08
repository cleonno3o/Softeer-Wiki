import requests
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
    with open('./W1/M3/data/team_etl_project_log.txt', 'a') as log:
        time = dt.datetime.now().strftime('%Y-%b-%d-%H-%M-%S')
        if is_start:
            log.write(f'{time}, [{state.value}] Started\n')
        else:
            log.write(f'{time}, [{state.value}] Ended\n')
    log.close()

def print_query_result(query:str):
    con = sqlite3.connect('./W1/M3/data/team_World_Economies.db')
    cursor = con.cursor()
    data = cursor.execute(query).fetchall()
    formatted_data = [
    [f"{x:,.2f}" if isinstance(x, float) else x for x in row]
    for row in data
    ]
    columns = [description[0] for description in cursor.description]
    print(tabulate(formatted_data, headers=columns, tablefmt='grid'))
    con.close()

# [EXTRACT]
state = Mode.EXTRACT
write_log(state, True)

## API에서 데이터 가져오기
### GDP 데이터
gdp_data = requests.get('https://www.imf.org/external/datamapper/api/v1/NGDPD?periods=2025,2025')
### 국가 그룹 데이터
group_data = requests.get('https://www.imf.org/external/datamapper/api/v1/groups')
### 리전 데이터
region_data = requests.get('https://www.imf.org/external/datamapper/api/v1/regions')

## 원본 데이터 저장
with open('./W1/M3/data/team_gdp.json','w', encoding='utf-8') as gdp_file:
    json.dump(gdp_data.text, gdp_file, indent=4)
gdp_file.close()

with open('./W1/M3/data/team_group.json','w', encoding='utf-8') as group_file:
    json.dump(group_data.text, group_file, indent=4)
group_file.close()

with open('./W1/M3/data/team_region.json','w', encoding='utf-8') as region_file:
    json.dump(region_data.text, region_file, indent=4)
region_file.close()

write_log(state, False)
state = Mode.TRANSFORM

# [TRANSFORM]
write_log(state, True)

## json 객체로 변환
gdp_json_obejct = json.loads(gdp_data.text)
group_json_object = json.loads(group_data.text)
region_json_object = json.loads(region_data.text)

## API에서 받은 JSON 데이터를 DataFrame으로 변환
gdp_df = pd.DataFrame(gdp_json_obejct['values']['NGDPD'])
group_df = pd.DataFrame(group_json_object['groups'])
region_df = pd.DataFrame(region_json_object['regions'])

## DataFrame을 목적에 맞게 수정(컬럼이름, 소수점)
gdp_df = pd.melt(gdp_df)
gdp_df.rename(columns={'variable':'Country', 'value':'GDP_USD_billion'},inplace=True)
gdp_df.sort_values(by='GDP_USD_billion',ascending=False, inplace=True)
gdp_df['GDP_USD_billion'] = round(gdp_df['GDP_USD_billion'], 2)
gdp_df.reset_index(inplace=True, drop=True)

group_df = pd.melt(group_df)
group_df.rename(columns={'variable':'group','value':'mean'}, inplace=True)

region_df = pd.melt(region_df)
region_df.rename(columns={'variable':'region','value':'mean'}, inplace=True)

## 국가가 아닌 데이터 제거
gdp_df = gdp_df[~gdp_df['Country'].isin(group_df['group'])]
gdp_df = gdp_df[~gdp_df['Country'].isin(region_df['region'])]
gdp_df.reset_index(inplace=True, drop=True)

## 국가별 대륙 매칭
region_info_df = pd.read_csv('./W1/M3/data/region.csv')
gdp_df = gdp_df.merge(
    region_info_df[['alpha-3','region']],
    left_on='Country',
    right_on='alpha-3',
    how='left'
    )
gdp_df.drop(columns='alpha-3', inplace=True)

write_log(state, False)
state = Mode.LOAD

# [LOAD]
write_log(state, True)

## DB에 DataFrame 저장
con = sqlite3.connect('./W1/M3/data/team_World_Economies.db')
gdp_df.to_sql('gdp',con, if_exists='replace')
con.close()

write_log(state, False)

## [Query를 사용해 출력하기]
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
            ROW_NUMBER() OVER (PARTITION BY region ORDER BY GDP_USD_billion DESC) AS rank
        FROM gdp
    )
    SELECT region, AVG(GDP_USD_billion)
    FROM rankedByRegionGdp
    WHERE rank <= 5
    GROUP BY region;
    '''
)